# backend/app/ai.py

"""
Main application for the agent.

Owns the long-lived MCP subprocess + ClientSession and the GenAI client for
the entire process lifetime via FastAPI's lifespan. Per-request code should
read these from `app.agent.runtime.runtime` rather than re-creating them.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.api.router import router
from app.agent.core.runtime import agent_runtime_context
from app.core.config import settings
from app.utils.http import close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with agent_runtime_context():
            yield
    finally:
        await close_http_client()


app = FastAPI(
    title=settings.AGENT_NAME,
    version=settings.AGENT_VERSION,
    lifespan=lifespan,
)

# Allow React (Port 5173) to talk to Python
origins = [
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ----------------------

# Include all our routes
app.include_router(router, prefix="/agent/api/v1")
