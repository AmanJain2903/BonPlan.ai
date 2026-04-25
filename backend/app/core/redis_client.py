# backend/app/core/redis_client.py

"""
Async Redis client for the BonPlan.ai backend.

Used primarily by the surgical SKU rate limiter, but exposed as a generic
connection factory so anything else in the backend/agent process can reuse
the same pool.

Connection rules:
- One shared asyncio connection pool per process (lazy-initialised).
- `get_redis()` always returns the same `redis.asyncio.Redis` instance.
- `close_redis()` is idempotent and safe to call from FastAPI lifespan.
- The client decodes responses to str by default, except when a command
  needs raw bytes — Redis auto-handles that.
"""

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool
from redis.exceptions import RedisError

from app.core.config import settings
from app.logging import get_core_logger

logger = get_core_logger("redis_client")

_pool: Optional[ConnectionPool] = None
_client: Optional[redis.Redis] = None


def _build_pool() -> ConnectionPool:
    return ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=64,
        health_check_interval=30,
    )


def get_redis() -> redis.Redis:
    """Return the process-wide async Redis client (lazily created)."""
    global _pool, _client
    if _client is None:
        _pool = _build_pool()
        _client = redis.Redis(connection_pool=_pool)
    return _client


async def ping_redis() -> bool:
    """Returns True if Redis is reachable. Used in app startup."""
    try:
        client = get_redis()
        return await client.ping()
    except RedisError as e:
        logger.warning("Redis ping failed", error=str(e))
        return False


async def close_redis() -> None:
    """Tear down the client and pool. Idempotent."""
    global _client, _pool
    if _client is not None:
        try:
            await _client.aclose()
        except Exception as e:
            logger.warning("Error closing Redis client", error=str(e))
        _client = None
    if _pool is not None:
        try:
            await _pool.disconnect(inuse_connections=True)
        except Exception as e:
            logger.warning("Error disconnecting Redis pool", error=str(e))
        _pool = None
