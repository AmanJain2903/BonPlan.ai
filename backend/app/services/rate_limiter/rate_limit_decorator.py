# backend/app/services/rate_limit_decorator.py

"""
`@limit_sku(...)` decorator — thin wrapper over `RateLimiter.consume()` for
tools and endpoints that don't already have an inline cache layer.

Usage:

    @limit_sku("timezone")
    async def get_timezone(...): ...

    @limit_sku(resolver=resolve_get_route_sku)
    async def get_route(..., routing_preference=..., optimize_waypoint_order=...): ...

For tools that DO have inline caching (search_places, get_coordinates, etc.)
call `await get_rate_limiter().consume(sku, cache_hit=..., user_id=...)`
directly after the cache check. The decorator is deliberately limited to the
simple case so we don't build a leaky abstraction around the existing cache
helpers.

On limit breach the decorator converts `RateLimitExceeded` to a dict with
`{"error": "...", "sku": ..., "retry_after_seconds": ..., "status_code": 429}`
for MCP tools (they return dicts, not raise), and to an HTTPException(429)
for FastAPI endpoints (detected by whether the wrapped function lives under
`app.api.v1.endpoints`).
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import HTTPException

from app.services.rate_limiter.rate_limiter import (
    ConsumeResult,
    RateLimitExceeded,
    get_rate_limiter,
)
from app.services.rate_limiter.sku_resolver import SkuResolver

logger = logging.getLogger(__name__)


def _is_endpoint(func: Callable[..., Any]) -> bool:
    module = getattr(func, "__module__", "") or ""
    return ".api.v1.endpoints" in module or ".api.v1." in module


def _raise_for_endpoint(exc: RateLimitExceeded) -> None:
    raise HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded.",
            "sku": exc.sku,
            "limit": exc.limit,
            "current": exc.current,
            "retry_after_seconds": exc.retry_after_seconds,
            "scope": exc.scope,
        },
        headers={"Retry-After": str(max(1, exc.retry_after_seconds))},
    )


def _error_dict_for_tool(exc: RateLimitExceeded) -> dict:
    return {
        "error": "Rate limit exceeded.",
        "sku": exc.sku,
        "limit": exc.limit,
        "current": exc.current,
        "retry_after_seconds": exc.retry_after_seconds,
        "scope": exc.scope,
        "status_code": 429,
        "fix_hint": "The monthly/daily quota for this SKU is exhausted. Do not retry; continue without this tool and inform the user if the feature is blocked.",
    }


def limit_sku(
    sku: Optional[str] = None,
    *,
    resolver: Optional[SkuResolver] = None,
    user_id_arg: Optional[str] = None,
    cache_hit_arg: Optional[str] = "cache_hit",
):
    """
    Decorator factory.

    Args:
        sku: Static SKU name (when the SKU does not depend on call args).
        resolver: Callable(**kwargs) -> sku_name for context-aware SKU choice.
                  Exactly one of `sku` or `resolver` must be supplied.
        user_id_arg: Name of the kwarg carrying the user UUID for USER-scoped
                     SKUs. If None, the call is counted as global.
        cache_hit_arg: Name of a kwarg that signals an upstream cache hit;
                      when truthy, the limiter is skipped entirely. Callers
                      that don't pass this arg simply don't skip.
    """
    if (sku is None) == (resolver is None):
        raise ValueError("Exactly one of `sku` or `resolver` must be supplied.")

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if not inspect.iscoroutinefunction(func):
            raise TypeError("@limit_sku only supports async functions.")

        is_endpoint = _is_endpoint(func)
        sig = inspect.signature(func)

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Bind args so we can inspect them regardless of whether they
            # were passed positionally or as kwargs.
            try:
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                bound_args = dict(bound.arguments)
            except TypeError:
                bound_args = dict(kwargs)

            cache_hit = bool(bound_args.get(cache_hit_arg)) if cache_hit_arg else False
            user_id_raw = bound_args.get(user_id_arg) if user_id_arg else None
            user_id: Optional[UUID] = None
            if isinstance(user_id_raw, UUID):
                user_id = user_id_raw
            elif isinstance(user_id_raw, str) and user_id_raw:
                try:
                    user_id = UUID(user_id_raw)
                except ValueError:
                    user_id = None

            resolved_sku = sku if sku is not None else resolver(**bound_args)

            limiter = get_rate_limiter()
            try:
                result: ConsumeResult = await limiter.consume(
                    resolved_sku,
                    user_id=user_id,
                    cache_hit=cache_hit,
                    raise_on_limit=True,
                )
            except RateLimitExceeded as exc:
                if is_endpoint:
                    _raise_for_endpoint(exc)
                return _error_dict_for_tool(exc)

            logger.debug(
                "SKU '%s' consume: current=%s remaining=%s allowed=%s skipped=%s",
                result.sku,
                result.current,
                result.remaining,
                result.allowed,
                result.skipped,
            )

            return await func(*args, **kwargs)

        wrapper.__rate_limit_sku__ = sku  # type: ignore[attr-defined]
        wrapper.__rate_limit_resolver__ = resolver  # type: ignore[attr-defined]
        return wrapper

    return decorator
