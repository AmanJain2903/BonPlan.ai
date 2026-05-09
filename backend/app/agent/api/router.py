# backend/app/agent/api/router.py

"""
This file contains the router for the agent API endpoints.
"""

from fastapi import APIRouter

from app.agent.api.v1.endpoints.api_cache import router as api_cache_router
from app.agent.api.v1.endpoints.chat import router as chat_router
from app.agent.api.v1.endpoints.solo_planner import router as solo_planner_router
from app.agent.api.v1.endpoints.sync import router as sync_router

router = APIRouter()

router.include_router(api_cache_router, prefix="/api-cache", tags=["api-cache"])
router.include_router(solo_planner_router, prefix="/solo-planner", tags=["solo-planner"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(sync_router, prefix="/sync", tags=["sync"])
