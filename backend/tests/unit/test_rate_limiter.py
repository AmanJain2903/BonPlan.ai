import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from redis.exceptions import RedisError

from app.database.models.rateLimitConfigs import Period, Scope
from app.services.rate_limiter import rate_limit_decorator as decorator
from app.services.rate_limiter import rate_limiter as rl
from app.services.rate_limiter import sku_resolver


def run(coro):
    return asyncio.run(coro)


class StaticConfigCache:
    def __init__(self, snap):
        self.snap = snap
        self.invalidated = False

    async def get(self, sku):
        return self.snap

    async def invalidate(self):
        self.invalidated = True


class FakeRedis:
    def __init__(self, eval_result=(1, 2, 60), value="2", ttl=60, deleted=1, fail=None):
        self.eval_result = eval_result
        self.value = value
        self.ttl_value = ttl
        self.deleted = deleted
        self.fail = fail
        self.calls = []

    async def script_load(self, script):
        self.calls.append(("script_load", script[:20]))
        return "sha"

    async def evalsha(self, *args):
        self.calls.append(("evalsha", args))
        if self.fail:
            raise self.fail
        return self.eval_result

    async def get(self, key):
        self.calls.append(("get", key))
        if self.fail:
            raise self.fail
        return self.value

    async def ttl(self, key):
        self.calls.append(("ttl", key))
        return self.ttl_value

    async def delete(self, key):
        self.calls.append(("delete", key))
        return self.deleted


def make_snap(**overrides):
    base = dict(
        sku="routes_compute_routes_pro",
        sku_id=uuid4(),
        limit=5,
        period=Period.MONTHLY,
        scope=Scope.GLOBAL,
        reset_minute=0,
        reset_hour=0,
        reset_day=1,
        reset_month=1,
    )
    base.update(overrides)
    return rl.RateLimitConfigSnapshot(**base)


def test_period_window_labels_and_ttl():
    tz = ZoneInfo("America/Los_Angeles")
    now = datetime(2026, 5, 8, 10, 0, tzinfo=tz)
    start, end = rl._compute_period_window(Period.DAILY, 1, 1, 9, 30, now)
    assert start.hour == 9 and start.minute == 30
    assert end > now
    assert rl._period_bucket_label(Period.DAILY, start) == "20260508"
    assert rl._ttl_seconds_from_window(end, now) > 0

    start, _ = rl._compute_period_window(Period.MONTHLY, 1, 31, 0, 0, datetime(2026, 2, 15, tzinfo=tz))
    assert start.day == 31 and start.month == 1


def test_sku_resolution_branches():
    assert sku_resolver.resolve_get_route_sku(routing_preference="TRAFFIC_UNAWARE", optimize_waypoint_order=False) == "routes_compute_routes_essentials"
    assert sku_resolver.resolve_get_route_sku(routing_preference="TRAFFIC_AWARE") == "routes_compute_routes_pro"
    assert sku_resolver.resolve_search_places_sku(include_amenities=True) == "places_text_search_enterprise_atmosphere"
    assert sku_resolver.resolve_sku("missing_tool") is None
    assert sku_resolver.resolve_llm_model_sku("vendor/New Model!") == "llm_vendor_new_model"


def test_consume_cache_hit_skips_redis():
    limiter = rl.RateLimiter()
    result = run(limiter.consume("Any SKU", cache_hit=True))
    assert result.allowed is True
    assert result.skipped is True
    assert result.sku == "any sku"


def test_consume_allowed_uses_redis_and_normalizes(monkeypatch):
    snap = make_snap()
    fake_redis = FakeRedis(eval_result=(1, 3, 120))
    limiter = rl.RateLimiter()
    limiter._config_cache = StaticConfigCache(snap)
    limiter._script_sha = "sha"
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)
    monkeypatch.setattr(rl.asyncio, "create_task", lambda coro: coro.close())

    result = run(limiter.consume("Routes_Compute_Routes_Pro"))

    assert result.allowed is True
    assert result.current == 3
    assert result.remaining == 2
    assert result.period == "monthly"
    assert fake_redis.calls[0][0] == "evalsha"


def test_consume_over_limit_raises(monkeypatch):
    snap = make_snap(limit=2)
    limiter = rl.RateLimiter()
    limiter._config_cache = StaticConfigCache(snap)
    limiter._script_sha = "sha"
    monkeypatch.setattr(rl, "get_redis", lambda: FakeRedis(eval_result=(0, 2, 55)))

    with pytest.raises(rl.RateLimitExceeded) as exc:
        run(limiter.consume("routes_compute_routes_pro"))

    assert exc.value.status_code if hasattr(exc.value, "status_code") else True
    assert exc.value.sku == "routes_compute_routes_pro"
    assert exc.value.retry_after_seconds == 55


def test_missing_config_lenient_and_strict(monkeypatch):
    limiter = rl.RateLimiter()
    limiter._config_cache = StaticConfigCache(None)
    monkeypatch.setattr(rl.settings, "RATE_LIMITER_MODE", "lenient")
    result = run(limiter.consume("unknown"))
    assert result.skipped is True

    monkeypatch.setattr(rl.settings, "RATE_LIMITER_MODE", "strict")
    with pytest.raises(rl.RateLimitExceeded):
        run(limiter.consume("unknown"))


def test_get_status_and_reset_use_mock_redis(monkeypatch):
    snap = make_snap(limit=5)
    fake_redis = FakeRedis(value="4", ttl=30, deleted=1)
    limiter = rl.RateLimiter()
    limiter._config_cache = StaticConfigCache(snap)
    monkeypatch.setattr(rl, "get_redis", lambda: fake_redis)

    status = run(limiter.get_status("routes_compute_routes_pro"))
    assert status.current == 4
    assert status.remaining == 1
    assert status.allowed is True
    assert run(limiter.reset("routes_compute_routes_pro")) is True


def test_redis_error_lenient_fails_open(monkeypatch):
    snap = make_snap(limit=5)
    limiter = rl.RateLimiter()
    limiter._config_cache = StaticConfigCache(snap)
    limiter._script_sha = "sha"
    monkeypatch.setattr(rl.settings, "RATE_LIMITER_MODE", "lenient")
    monkeypatch.setattr(rl, "get_redis", lambda: FakeRedis(fail=RedisError("down")))

    result = run(limiter.consume("routes_compute_routes_pro"))
    assert result.allowed is True
    assert result.skipped is True


def test_decorator_converts_limits_for_tools(monkeypatch):
    exc = rl.RateLimitExceeded("sku", 1, 1, 60, "global")

    class DenyingLimiter:
        async def consume(self, *args, **kwargs):
            raise exc

    monkeypatch.setattr(decorator, "get_rate_limiter", lambda: DenyingLimiter())

    @decorator.limit_sku("sku")
    async def tool(cache_hit=False):
        return {"ok": True}

    result = run(tool())
    assert result["status_code"] == 429
    assert result["sku"] == "sku"


def test_decorator_skips_when_cache_hit(monkeypatch):
    calls = []

    class AllowingLimiter:
        async def consume(self, *args, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(allowed=True)

    monkeypatch.setattr(decorator, "get_rate_limiter", lambda: AllowingLimiter())

    @decorator.limit_sku("sku")
    async def tool(cache_hit=False):
        return {"ok": True}

    assert run(tool(cache_hit=True)) == {"ok": True}
    assert calls[0]["cache_hit"] is True
