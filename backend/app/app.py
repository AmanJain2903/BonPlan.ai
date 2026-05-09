# backend/app/app.py

"""
This file contains the main application for the backend application.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import settings
from app.core.redis_client import close_redis, ping_redis
from app.database.database import Base, engine
from app.database import models  # noqa: F401 - ensure models are registered with Base
from app.logging import get_app_logger
from app.services.rate_limiter.rate_limiter import get_rate_limiter
from app.services.rate_limiter.usage_cleanup import usage_cleanup_task
from app.services.trip_lifecycle import trip_lifecycle_task
from app.services.trip_status_emailer import trip_status_email_task
from app.services.keepalive import keepalive_task
from app.utils.http import close_http_client
import asyncio

logger = get_app_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = None
    lifecycle_task = None
    trip_email_task = None
    keepalive_task_obj = None
    logger.info("Lifespan starting", project=settings.PROJECT_NAME, version=settings.PROJECT_VERSION)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema ensured")

    # Restore Redis counters from Postgres for the active period buckets so
    # that a Redis restart doesn't hand free quota back to clients.
    try:
        restored = await get_rate_limiter().restore_counters_from_db()
        logger.info("Rate-limit Redis restore complete", keys_restored=restored)
    except Exception:
        logger.exception("Rate-limit Redis restore failed")

    # Warm the rate-limiter (loads the Lua script into Redis) and verify
    # connectivity. If Redis is down we still start the app, but the limiter
    # will fail-open / fail-closed based on RATE_LIMITER_MODE.
    redis_ok = await ping_redis()
    if redis_ok:
        try:
            await get_rate_limiter().load_script()
            logger.info("Rate limiter Lua script loaded")
        except Exception as e:
            logger.warning("Rate limiter Lua load failed", error=str(e))
    else:
        logger.warning(
            "Redis unreachable at startup",
            mode=settings.RATE_LIMITER_MODE,
        )

    # Start the background usage cleanup task
    cleanup_task = asyncio.create_task(usage_cleanup_task())
    logger.info("Usage cleanup task scheduled")

    # Start the trip lifecycle task (auto-transition DRAFT→delete, GENERATED→CURRENT, active→COMPLETED)
    lifecycle_task = asyncio.create_task(trip_lifecycle_task())
    logger.info("Trip lifecycle task scheduled")

    trip_email_task = asyncio.create_task(trip_status_email_task())
    logger.info("Trip status email task scheduled")

    # Start the keepalive task
    keepalive_task_obj = asyncio.create_task(keepalive_task(f"{settings.AGENT_URL}/agent/api/v1/sync/telemetry", "agent", settings.KEEPALIVE_INTERVAL_SECONDS))
    logger.info("Keepalive task scheduled for agent")

    # Start the keepalive task
    keepalive_task_obj = asyncio.create_task(keepalive_task(f"{settings.MCP_URL}/api/v1/sync/mcp", "mcp", settings.KEEPALIVE_INTERVAL_SECONDS))
    logger.info("Keepalive task scheduled for MCP")

    try:
        yield
    finally:
        logger.info("Lifespan shutting down")
        if cleanup_task:
            cleanup_task.cancel()
        if lifecycle_task:
            lifecycle_task.cancel()
        if trip_email_task:
            trip_email_task.cancel()
        if keepalive_task_obj:
            keepalive_task_obj.cancel()
        await close_http_client()
        await close_redis()
        await engine.dispose()
        logger.info("Lifespan shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
)

# Allow React (Port 5173) to talk to Python
origins = [
    settings.FRONTEND_URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)
# ----------------------

# Include all our routes
app.include_router(router, prefix="/api/v1")
