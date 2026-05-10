# backend/app/ai.py

"""
Main application for the agent.

Owns the long-lived remote MCP SSE session and the LiteLLM client for the
entire process lifetime via FastAPI's lifespan. Per-request code should read
these from `app.agent.runtime.runtime` rather than re-creating them.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.api.router import router
from app.agent.core.runtime import agent_runtime_context
from app.core.config import settings
from app.logging import get_app_logger
from app.utils.http import close_http_client
import asyncio

logger = get_app_logger("ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agent lifespan starting", agent=settings.AGENT_NAME, version=settings.AGENT_VERSION)
    try:
        async with agent_runtime_context():
            logger.info("Agent runtime context entered")
            yield
    except Exception:
        logger.exception("Agent lifespan crashed")
        raise
    finally:
        logger.info("Agent lifespan shutting down")
        await close_http_client()
        logger.info("Agent lifespan shutdown complete")


app = FastAPI(
    title=settings.AGENT_NAME,
    version=settings.AGENT_VERSION,
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
    expose_headers=["*"],
)
# ----------------------

# Include all our routes
app.include_router(router, prefix="/agent/api/v1")
