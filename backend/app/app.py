# backend/app/app.py

"""
This file contains the main application for the backend application.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import settings
from app.database.database import Base, engine
from app.database import models  # noqa: F401 - ensure models are registered with Base
from app.utils.http import close_http_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # <--- DELETE DATA
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
        await close_http_client()
        await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
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
    allow_headers=["*"]
)
# ----------------------

# Include all our routes
app.include_router(router, prefix="/api/v1")
