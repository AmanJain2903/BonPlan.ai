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
from app.services.rate_limiter.rate_limiter import get_rate_limiter
from app.services.rate_limiter.usage_cleanup import usage_cleanup_task
from app.utils.http import close_http_client
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = None
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # <--- DELETE DATA
        await conn.run_sync(Base.metadata.create_all)



    # Restore Redis counters from Postgres for the active period buckets so
    # that a Redis restart doesn't hand free quota back to clients.
    import logging
    try:
        restored = await get_rate_limiter().restore_counters_from_db()
        logging.getLogger(__name__).info("Rate-limit Redis restore: %s keys", restored)
    except Exception:
        logging.getLogger(__name__).exception("Rate-limit Redis restore failed")

    # Warm the rate-limiter (loads the Lua script into Redis) and verify
    # connectivity. If Redis is down we still start the app, but the limiter
    # will fail-open / fail-closed based on RATE_LIMITER_MODE.
    redis_ok = await ping_redis()
    if redis_ok:
        try:
            await get_rate_limiter().load_script()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Rate limiter Lua load failed: %s", e)
    else:
        import logging
        logging.getLogger(__name__).warning(
            "Redis unreachable at startup — rate limiter will operate in '%s' mode.",
            settings.RATE_LIMITER_MODE,
        )

    # Start the background usage cleanup task
    cleanup_task = asyncio.create_task(usage_cleanup_task())

    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
        await close_http_client()
        await close_redis()
        await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    lifespan=lifespan,
)

# Allow React (Port 5173) to talk to Python
origins = [
    settings.FRONTEND_URL,
    settings.ADMIN_URL,
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
