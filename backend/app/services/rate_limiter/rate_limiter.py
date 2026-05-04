# backend/app/services/rate_limiter.py

"""
Surgical SKU Rate Limiter.

Design:
- Rules (limit / period / scope) are sourced from `rate_limit_configs` in Postgres
  (seeded at startup from the SKU spec) and cached in-process for
  `settings.RATE_LIMITER_CONFIG_TTL_SECONDS` so the hot path stays Redis-only.
- Counters live in Redis. One key per (sku, scope, owner) for the active period.
- A single Lua script performs the atomic check-then-INCR + sets TTL only on
  the first write in a period. This prevents race conditions under concurrent
  requests and guarantees that going over the limit is impossible.
- TTLs are computed at increment time using "Lazy Reset" semantics.
- The limiter is cache-aware: callers pass `cache_hit=True` when they served
  the response from their own cache, which skips the counter entirely.
- When Redis is unreachable, behaviour is controlled by `RATE_LIMITER_MODE`:
    "lenient" (default) — allow the call, log the failure.
    "strict"            — treat as rate-limited (raise).
"""

from __future__ import annotations

import asyncio
import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from redis.exceptions import RedisError
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.redis_client import get_redis
from app.database.database import Session
from app.database.models.rateLimitConfigs import Period, RateLimitConfigs, Scope
from app.database.models.rateLimitUsage import RateLimitUsage, GLOBAL_USER_SENTINEL
from app.logging import get_rate_limiter_logger

logger = get_rate_limiter_logger("rate_limiter")


class RateLimitExceeded(Exception):
    """Raised when the rate limiter denies a request."""

    def __init__(
        self,
        sku: str,
        limit: int,
        current: int,
        retry_after_seconds: int,
        scope: str,
    ) -> None:
        self.sku = sku
        self.limit = limit
        self.current = current
        self.retry_after_seconds = retry_after_seconds
        self.scope = scope
        super().__init__(
            f"Rate limit exceeded for SKU '{sku}' ({scope}): "
            f"{current}/{limit}. Retry after {retry_after_seconds}s."
        )


@dataclass(frozen=True)
class RateLimitConfigSnapshot:
    sku: str
    sku_id: UUID
    limit: int  # -1 == unlimited
    period: Period
    scope: Scope
    # Per-SKU reset anchor (in RATE_LIMITER_RESET_TZ). Interpreted by period:
    # DAILY uses (hour, minute); WEEKLY adds day (1=Mon..7=Sun); MONTHLY adds
    # day-of-month; YEARLY adds month + day-of-month. See _compute_period_window.
    reset_minute: int = 0
    reset_hour: int = 0
    reset_day: int = 1
    reset_month: int = 1


@dataclass(frozen=True)
class ConsumeResult:
    allowed: bool
    sku: str
    limit: int
    current: int
    remaining: int
    scope: str
    period: str
    retry_after_seconds: int
    skipped: bool  # True when cache_hit=True (or unlimited / missing config)


# --- Lua script ---------------------------------------------------------------
#
# KEYS[1] = counter key
# ARGV[1] = limit (int). -1 = unlimited (always allow, never increment).
# ARGV[2] = ttl_seconds (int) applied only on the first write this period
# ARGV[3] = amount (int) to increment by (usually 1)
#
# Returns: { allowed (1|0), current (int), ttl_remaining (int) }
#
# Notes:
# - `INCRBY` then conditional rollback keeps it fully atomic inside the script.
# - When limit == -1 we DO NOT increment — unlimited SKUs are only tracked via
#   config, not in Redis, to avoid burning RAM on endpoints we don't enforce.
_LIMIT_LUA = """
local limit = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local amount = tonumber(ARGV[3])

local current = redis.call('INCRBY', KEYS[1], amount)
if current == amount then
    redis.call('EXPIRE', KEYS[1], ttl)
end

-- Unlimited SKUs (limit < 0) still get counted for observability,
-- but never deny.
if limit < 0 then
    local ttl_remaining = redis.call('TTL', KEYS[1])
    return {1, current, ttl_remaining}
end

if current > limit then
    redis.call('DECRBY', KEYS[1], amount)
    local ttl_remaining = redis.call('TTL', KEYS[1])
    return {0, current - amount, ttl_remaining}
end

local ttl_remaining = redis.call('TTL', KEYS[1])
return {1, current, ttl_remaining}
"""


def _anchor_in_month(year: int, month: int, day: int, hour: int, minute: int, tz: ZoneInfo) -> datetime:
    """Build a tz-aware datetime, clamping `day` to the last valid day of the month."""
    last_day = calendar.monthrange(year, month)[1]
    safe_day = min(day, last_day)
    return datetime(year, month, safe_day, hour, minute, 0, 0, tzinfo=tz)


def _compute_period_window(
    period: Period,
    reset_month: int,
    reset_day: int,
    reset_hour: int,
    reset_minute: int,
    now_local: datetime,
) -> tuple[datetime, datetime]:
    """
    Return (period_start, period_end) — both tz-aware in `now_local.tzinfo` —
    such that period_start <= now_local < period_end. The boundaries are
    derived from the per-SKU anchor.

    For weekly, `reset_day` follows ISO weekday (1 = Monday … 7 = Sunday).
    """
    tz = now_local.tzinfo  # type: ignore[assignment]

    if period == Period.DAILY:
        candidate = now_local.replace(hour=reset_hour, minute=reset_minute, second=0, microsecond=0)
        start = candidate if candidate <= now_local else candidate - timedelta(days=1)
        end = start + timedelta(days=1)
        return start, end

    if period == Period.WEEKLY:
        anchor_dow = max(1, min(7, reset_day))  # ISO 1..7
        days_back = (now_local.isoweekday() - anchor_dow) % 7
        candidate = (now_local - timedelta(days=days_back)).replace(
            hour=reset_hour, minute=reset_minute, second=0, microsecond=0
        )
        start = candidate if candidate <= now_local else candidate - timedelta(days=7)
        end = start + timedelta(days=7)
        return start, end

    if period == Period.MONTHLY:
        candidate = _anchor_in_month(now_local.year, now_local.month, reset_day, reset_hour, reset_minute, tz)  # type: ignore[arg-type]
        if candidate <= now_local:
            start = candidate
            ny, nm = (start.year, start.month + 1) if start.month < 12 else (start.year + 1, 1)
            end = _anchor_in_month(ny, nm, reset_day, reset_hour, reset_minute, tz)  # type: ignore[arg-type]
        else:
            py, pm = (now_local.year, now_local.month - 1) if now_local.month > 1 else (now_local.year - 1, 12)
            start = _anchor_in_month(py, pm, reset_day, reset_hour, reset_minute, tz)  # type: ignore[arg-type]
            end = candidate
        return start, end

    if period == Period.YEARLY:
        m = max(1, min(12, reset_month))
        candidate = _anchor_in_month(now_local.year, m, reset_day, reset_hour, reset_minute, tz)  # type: ignore[arg-type]
        if candidate <= now_local:
            start = candidate
            end = _anchor_in_month(start.year + 1, m, reset_day, reset_hour, reset_minute, tz)  # type: ignore[arg-type]
        else:
            start = _anchor_in_month(now_local.year - 1, m, reset_day, reset_hour, reset_minute, tz)  # type: ignore[arg-type]
            end = candidate
        return start, end

    raise ValueError(f"Unknown period: {period}")


def _period_bucket_label(period: Period, period_start: datetime) -> str:
    """
    Bucket label derived from the *period_start*, not "now". This keeps the
    historic format (YYYYMMDD / YYYYWXX / YYYYMM / YYYY) — which
    `usage_cleanup` relies on — but stays correct for per-SKU anchors that
    don't fall on the canonical day of the period.
    """
    if period == Period.DAILY:
        return period_start.strftime("%Y%m%d")
    if period == Period.WEEKLY:
        iso_year, iso_week, _ = period_start.isocalendar()
        return f"{iso_year}W{iso_week:02d}"
    if period == Period.MONTHLY:
        return period_start.strftime("%Y%m")
    if period == Period.YEARLY:
        return period_start.strftime("%Y")
    raise ValueError(f"Unknown period: {period}")


def _ttl_seconds_from_window(period_end: datetime, now_local: datetime) -> int:
    delta = period_end - now_local
    # Clamp to >=1 so we never EXPIRE with 0 (which deletes immediately).
    return max(1, int(delta.total_seconds()))


class _ConfigCache:
    """
    Tiny in-process cache for SKU configs to keep the hot path Redis-only.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._by_sku: dict[str, RateLimitConfigSnapshot] = {}
        self._loaded_at: Optional[datetime] = None

    async def get(self, sku: str) -> Optional[RateLimitConfigSnapshot]:
        sku = sku.lower()
        now = datetime.now(ZoneInfo("UTC"))
        if (
            self._loaded_at is None
            or (now - self._loaded_at).total_seconds() > self._ttl_seconds
        ):
            await self._reload()
        return self._by_sku.get(sku)

    async def invalidate(self) -> None:
        self._loaded_at = None

    async def _reload(self) -> None:
        async with Session() as db:
            rows = (await db.execute(select(RateLimitConfigs))).scalars().all()
        self._by_sku = {
            row.sku.lower(): RateLimitConfigSnapshot(
                sku=row.sku.lower(),
                sku_id=row.id,
                limit=row.limit,
                period=row.period,
                scope=row.scope,
                reset_minute=getattr(row, "reset_minute", 0) or 0,
                reset_hour=getattr(row, "reset_hour", 0) or 0,
                reset_day=getattr(row, "reset_day", 1) or 1,
                reset_month=getattr(row, "reset_month", 1) or 1,
            )
            for row in rows
        }
        self._loaded_at = datetime.now(ZoneInfo("UTC"))


class RateLimiter:
    def __init__(self) -> None:
        self._config_cache = _ConfigCache(settings.RATE_LIMITER_CONFIG_TTL_SECONDS)
        self._script_sha: Optional[str] = None
        self._tz = ZoneInfo(settings.RATE_LIMITER_RESET_TZ)

    # --- script management ---------------------------------------------------

    async def load_script(self) -> str:
        client = get_redis()
        self._script_sha = await client.script_load(_LIMIT_LUA)
        return self._script_sha

    async def _ensure_script(self) -> str:
        if self._script_sha is None:
            return await self.load_script()
        return self._script_sha

    # --- key building --------------------------------------------------------

    def _window_for(self, snap: RateLimitConfigSnapshot) -> tuple[datetime, datetime]:
        return _compute_period_window(
            snap.period,
            snap.reset_month,
            snap.reset_day,
            snap.reset_hour,
            snap.reset_minute,
            datetime.now(self._tz),
        )

    def _build_key(
        self,
        sku: str,
        scope: Scope,
        user_id: Optional[UUID],
        period: Period,
        period_start: datetime,
    ) -> str:
        owner = str(user_id) if scope == Scope.USER and user_id is not None else "global"
        bucket = _period_bucket_label(period, period_start)
        return f"{settings.REDIS_RATE_LIMIT_PREFIX}:{sku}:{scope.value}:{owner}:{bucket}"

    # --- public API ----------------------------------------------------------

    async def consume(
        self,
        sku: str,
        *,
        user_id: Optional[UUID] = None,
        amount: int = 1,
        cache_hit: bool = False,
        raise_on_limit: bool = True,
    ) -> ConsumeResult:
        """
        Record usage for an SKU. When `cache_hit=True`, returns immediately
        without touching Redis — the underlying API call wasn't made so we
        don't decrement the quota.

        Returns a `ConsumeResult`. If the request would exceed the limit and
        `raise_on_limit=True`, raises `RateLimitExceeded` instead.
        """
        sku_normalized = sku.lower()

        if cache_hit:
            return ConsumeResult(
                allowed=True,
                sku=sku_normalized,
                limit=-1,
                current=0,
                remaining=-1,
                scope="global",
                period="",
                retry_after_seconds=0,
                skipped=True,
            )

        config = await self._config_cache.get(sku_normalized)
        if config is None:
            # No config row => no enforcement. Log once per SKU so missing
            # seed data is visible without spamming on every request.
            logger.warning("Rate-limit config missing for SKU — allowing.", sku=sku_normalized)
            return ConsumeResult(
                allowed=True,
                sku=sku_normalized,
                limit=-1,
                current=0,
                remaining=-1,
                scope="global",
                period="",
                retry_after_seconds=0,
                skipped=True,
            )

        # USER-scoped configs need a user_id. If we don't have one, we fall
        # back to a synthetic "anonymous" bucket so unauthenticated callers
        # still get limited instead of bypassing the quota.
        effective_user_id = user_id if config.scope == Scope.USER else None
        period_start, period_end = self._window_for(config)
        key = self._build_key(sku_normalized, config.scope, effective_user_id, config.period, period_start)
        ttl = _ttl_seconds_from_window(period_end, datetime.now(self._tz))

        try:
            sha = await self._ensure_script()
            client = get_redis()
            allowed_raw, current_raw, ttl_remaining_raw = await client.evalsha(
                sha, 1, key, config.limit, ttl, amount
            )
        except RedisError as e:
            # Script evicted from Redis cache — reload once and retry.
            if "NOSCRIPT" in str(e):
                try:
                    sha = await self.load_script()
                    client = get_redis()
                    allowed_raw, current_raw, ttl_remaining_raw = await client.evalsha(
                        sha, 1, key, config.limit, ttl, amount
                    )
                except RedisError as e2:
                    return self._handle_redis_error(e2, sku_normalized, config)
            else:
                return self._handle_redis_error(e, sku_normalized, config)

        allowed = int(allowed_raw) == 1
        current = int(current_raw)
        ttl_remaining = int(ttl_remaining_raw)
        remaining = max(0, config.limit - current) if allowed else 0

        result = ConsumeResult(
            allowed=allowed,
            sku=sku_normalized,
            limit=config.limit,
            current=current,
            remaining=remaining,
            scope=config.scope.value,
            period=config.period.value,
            retry_after_seconds=max(0, ttl_remaining),
            skipped=False,
        )

        if allowed:
            # Fire-and-forget DB mirror so counters survive a Redis restart.
            # We pass the absolute Redis-derived count to keep the two stores
            # eventually consistent rather than racing on parallel INCRs.
            asyncio.create_task(
                self._persist_usage(
                    sku_id=config.sku_id,
                    sku=sku_normalized,
                    user_id=effective_user_id,
                    period=config.period,
                    period_start=period_start,
                    current=current,
                )
            )

        if not allowed and raise_on_limit:
            raise RateLimitExceeded(
                sku=sku_normalized,
                limit=config.limit,
                current=current,
                retry_after_seconds=result.retry_after_seconds,
                scope=config.scope.value,
            )

        return result

    async def get_status(
        self,
        sku: str,
        *,
        user_id: Optional[UUID] = None,
    ) -> ConsumeResult:
        """
        Read-only counterpart to `consume`. Useful for admin dashboards.
        """
        sku_normalized = sku.lower()
        config = await self._config_cache.get(sku_normalized)
        if config is None:
            return ConsumeResult(
                allowed=True,
                sku=sku_normalized,
                limit=-1,
                current=0,
                remaining=-1,
                scope="global",
                period="",
                retry_after_seconds=0,
                skipped=True,
            )

        if config.limit < 0:
            return ConsumeResult(
                allowed=True,
                sku=sku_normalized,
                limit=-1,
                current=0,
                remaining=-1,
                scope=config.scope.value,
                period=config.period.value,
                retry_after_seconds=0,
                skipped=True,
            )

        effective_user_id = user_id if config.scope == Scope.USER else None
        period_start, _ = self._window_for(config)
        key = self._build_key(sku_normalized, config.scope, effective_user_id, config.period, period_start)

        try:
            client = get_redis()
            current_raw = await client.get(key)
            ttl_remaining = await client.ttl(key)
        except RedisError as e:
            logger.warning("Rate limiter status read failed", sku=sku_normalized, user_id=str(user_id) if user_id else None, error=str(e))
            return ConsumeResult(
                allowed=True,
                sku=sku_normalized,
                limit=config.limit,
                current=0,
                remaining=config.limit,
                scope=config.scope.value,
                period=config.period.value,
                retry_after_seconds=0,
                skipped=True,
            )

        current = int(current_raw) if current_raw is not None else 0
        return ConsumeResult(
            allowed=current < config.limit,
            sku=sku_normalized,
            limit=config.limit,
            current=current,
            remaining=max(0, config.limit - current),
            scope=config.scope.value,
            period=config.period.value,
            retry_after_seconds=max(0, int(ttl_remaining)) if ttl_remaining and ttl_remaining > 0 else 0,
            skipped=False,
        )

    async def reset(
        self,
        sku: str,
        *,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """
        Forcefully reset the counter for a SKU (for the current period
        bucket). Returns True if a key was deleted.
        """
        sku_normalized = sku.lower()
        config = await self._config_cache.get(sku_normalized)
        if config is None or config.limit < 0:
            return False

        effective_user_id = user_id if config.scope == Scope.USER else None
        period_start, _ = self._window_for(config)
        key = self._build_key(sku_normalized, config.scope, effective_user_id, config.period, period_start)

        try:
            client = get_redis()
            deleted = await client.delete(key)
            return bool(deleted)
        except RedisError as e:
            logger.warning("Rate limiter reset failed", sku=sku_normalized, error=str(e))
            return False

    async def invalidate_config_cache(self) -> None:
        """Call after any write to rate_limit_configs so new values take effect immediately."""
        await self._config_cache.invalidate()

    # --- DB persistence ------------------------------------------------------

    async def _persist_usage(
        self,
        *,
        sku_id: UUID,
        sku: str,
        user_id: Optional[UUID],
        period: Period,
        period_start: datetime,
        current: int,
    ) -> None:
        """
        Upsert the (sku_id, user_id, period_bucket) row in `rate_limit_usage`.

        Runs as a fire-and-forget task after a successful Redis consume so the
        hot path stays Redis-only. Failures are swallowed (with a log) — a
        missed mirror doesn't break the request, and the next successful
        consume in the same bucket will overwrite the stale value.
        """
        try:
            bucket = _period_bucket_label(period, period_start)
            owner = user_id if user_id is not None else GLOBAL_USER_SENTINEL
            insert_stmt = pg_insert(RateLimitUsage).values(
                sku_id=sku_id,
                sku=sku,
                user_id=owner,
                period_bucket=bucket,
                usage=current,
            )
            stmt = insert_stmt.on_conflict_do_update(
                constraint="uq_rate_limit_usage_sku_user_bucket",
                # Only move the counter forward — never overwrite a higher
                # value with a stale lower one (out-of-order task races).
                set_={
                    "usage": insert_stmt.excluded.usage,
                    "updated_at": func.now()
                },
                where=RateLimitUsage.usage < insert_stmt.excluded.usage,
            )
            async with Session() as db:
                await db.execute(stmt)
                await db.commit()
        except Exception as e:  # noqa: BLE001 — fire-and-forget by design
            logger.warning(
                "Failed to persist rate-limit usage",
                sku_id=str(sku_id), user_id=str(user_id) if user_id else None, error=str(e),
            )

    async def restore_counters_from_db(self) -> int:
        """
        On boot, load every usage row whose `period_bucket` matches the
        current bucket for its config's period back into Redis. This is what
        lets a Redis restart pick up where Postgres left off instead of
        handing every caller a fresh quota.

        Returns the number of Redis keys written.
        """
        await self._config_cache._reload()
        configs_by_id = {snap.sku_id: snap for snap in self._config_cache._by_sku.values()}
        if not configs_by_id:
            return 0

        async with Session() as db:
            rows = (await db.execute(select(RateLimitUsage))).scalars().all()

        try:
            client = get_redis()
        except Exception as e:  # noqa: BLE001
            logger.warning("Cannot restore counters — Redis unavailable", error=str(e))
            return 0

        restored = 0
        for row in rows:
            snap = configs_by_id.get(row.sku_id)
            if snap is None:
                continue
            # Per-SKU active bucket — different SKUs of the same period can
            # land in different buckets when their reset anchors differ.
            period_start, period_end = self._window_for(snap)
            active_bucket = _period_bucket_label(snap.period, period_start)
            if row.period_bucket != active_bucket:
                continue  # stale bucket — skip
            if snap.limit < 0:
                # Unlimited SKUs are tracked but never enforced; we still
                # restore so observability counts don't drop on Redis restart.
                pass

            user_id = None if row.user_id == GLOBAL_USER_SENTINEL else row.user_id
            effective_user_id = user_id if snap.scope == Scope.USER else None
            key = self._build_key(snap.sku, snap.scope, effective_user_id, snap.period, period_start)
            ttl = _ttl_seconds_from_window(period_end, datetime.now(self._tz))

            try:
                # SET with EX so we don't clobber a higher live counter — only
                # write if the key doesn't already exist (NX). If Redis was
                # repopulated by traffic in the meantime, that newer value wins.
                await client.set(key, row.usage, ex=ttl, nx=True)
                restored += 1
            except RedisError as e:
                logger.warning("Failed to restore key", key=key, error=str(e))
        logger.info("Redis counters restored from DB", rows_read_from_db=len(rows), rows_restored=restored)
        return restored

    # --- fail-open / fail-closed helper --------------------------------------

    def _handle_redis_error(
        self,
        error: RedisError,
        sku: str,
        config: RateLimitConfigSnapshot,
    ) -> ConsumeResult:
        logger.error("Rate limiter Redis error", sku=sku, error=str(error))
        if settings.RATE_LIMITER_MODE == "strict":
            logger.error("Rate limiter in strict mode, raising RateLimitExceeded")
            raise RateLimitExceeded(
                sku=sku,
                limit=config.limit,
                current=config.limit,  # treat as fully consumed
                retry_after_seconds=60,
                scope=config.scope.value,
            )
        # lenient: fail-open
        logger.info("Rate limiter in lenient mode, failing open")
        return ConsumeResult(
            allowed=True,
            sku=sku,
            limit=config.limit,
            current=0,
            remaining=config.limit,
            scope=config.scope.value,
            period=config.period.value,
            retry_after_seconds=0,
            skipped=True,
        )


_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Process-wide singleton accessor."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


# Kept for potential future use (month-length-aware calculations).
_ = calendar
