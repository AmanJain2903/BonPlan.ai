# backend/app/api/v1/endpoints/rate_limiting.py

"""
Rate-limiting endpoints for the BonPlan.ai backend.

Split into two groups:

1. **Config CRUD** — create/get/update/delete SKU rows in `rate_limit_configs`.
   These mutate the rule set; every write invalidates the in-process config
   cache so new limits take effect on the next request.

2. **Runtime** — inspect or mutate the live Redis counters:
   - GET  /status/{sku}           read current usage (optionally per-user)
   - POST /reset/{sku}            zero the counter for the active period
   - POST /consume/{sku}          manually increment (for scripts/backfills)
   - POST /track-client-sku       frontend-reported usage (Dynamic Maps,
                                  Directions, Autocomplete) — these SKUs
                                  bill client-side so the backend can only
                                  observe, not prevent.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, or_

from app.database.database import Session
from app.database.models.rateLimitConfigs import RateLimitConfigs
from app.database.models.rateLimitUsage import RateLimitUsage
from app.database.models.rateLimitConfigs import Period, Scope
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from typing import Optional
from uuid import UUID

router = APIRouter()

def _titlelize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("_", " ")
        return value.title()
    return None

@router.get("/client-skus", response_model=dict)
async def get_client_skus():
    """
    Returns all active SKUs dynamically so the frontend doesn't need to
    hardcode them. It filters configs that the frontend might use, or just returns all.
    """
    async with Session() as db:
        configs = (await db.execute(select(RateLimitConfigs))).scalars().all()
        client_skus = [
            {
                "sku": c.sku,
                "limit": c.limit,
                "period": c.period.value,
                "scope": c.scope.value
            } for c in configs
        ]
    return {"status_code": 200, "client_skus": client_skus}

# ---------------------------------------------------------------------------
# Runtime endpoints
# ---------------------------------------------------------------------------


class ConsumeBody(BaseModel):
    sku: str
    user_id: Optional[UUID] = None
    amount: int = 1
    cache_hit: bool = False


class ResetBody(BaseModel):
    sku: str
    user_id: Optional[UUID] = None


class TrackClientSkuBody(BaseModel):
    """Payload for frontend-reported SKUs that bill client-side.

    These are enforced as soft observations: if the counter is exhausted the
    server replies with 429 so the frontend can pause further renders, but
    Google has already billed the impression. Treat as best-effort
    observability rather than hard prevention.
    """
    sku: str
    count: int = 1


@router.get("/status/{sku}", response_model=dict)
async def get_rate_limit_status(sku: str, user_id: Optional[UUID] = Query(None)):
    """Read the current usage for a SKU without mutating it."""
    result = await get_rate_limiter().get_status(sku, user_id=user_id)
    return {
        "status_code": 200,
        "sku": _titlelize_optional(result.sku),
        "scope": result.scope,
        "period": result.period,
        "limit": result.limit,
        "current": result.current,
        "remaining": result.remaining,
        "allowed": result.allowed,
        "retry_after_seconds": result.retry_after_seconds,
        "skipped": result.skipped,
    }


@router.post("/reset", response_model=dict)
async def reset_rate_limit(data: ResetBody):
    """Force the counter for this SKU back to 0 for the current period."""
    deleted = await get_rate_limiter().reset(data.sku, user_id=data.user_id)
    return {"status_code": 200, "deleted": deleted, "sku": _titlelize_optional(data.sku)}


@router.post("/consume", response_model=dict)
async def consume_rate_limit(data: ConsumeBody):
    """
    Manually increment a SKU counter. Rarely needed in app code — the MCP
    tools and endpoints consume internally — but useful for backfills or
    admin scripts.
    """
    try:
        result = await get_rate_limiter().consume(
            data.sku,
            user_id=data.user_id,
            amount=data.amount,
            cache_hit=data.cache_hit,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded.",
                "sku": _titlelize_optional(exc.sku),
                "limit": exc.limit,
                "current": exc.current,
                "retry_after_seconds": exc.retry_after_seconds,
                "scope": exc.scope,
            },
            headers={"Retry-After": str(max(1, exc.retry_after_seconds))},
        )
    return {
        "status_code": 200,
        "sku": _titlelize_optional(result.sku),
        "allowed": result.allowed,
        "current": result.current,
        "remaining": result.remaining,
        "retry_after_seconds": result.retry_after_seconds,
        "skipped": result.skipped,
    }


@router.post("/track-client-sku", response_model=dict)
async def track_client_sku(data: TrackClientSkuBody):
    """
    Frontend-reported SKU usage — Dynamic Maps, Directions, Autocomplete
    keystrokes, Place Picker selections. These bill client-side via the
    Google JS SDK, so the backend can only observe; we still return 429
    once the quota is exhausted so the frontend can stop rendering.
    """
    try:
        result = await get_rate_limiter().consume(
            data.sku,
            amount=max(1, data.count),
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded.",
                "sku": _titlelize_optional(exc.sku),
                "limit": exc.limit,
                "current": exc.current,
                "retry_after_seconds": exc.retry_after_seconds,
            },
            headers={"Retry-After": str(max(1, exc.retry_after_seconds))},
        )
    return {
        "status_code": 200,
        "sku": _titlelize_optional(result.sku),
        "current": result.current,
        "remaining": result.remaining,
        "skipped": result.skipped,
    }