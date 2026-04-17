# backend/app/agent/api/router.py

"""
This file contains the router for the agent API endpoints.
"""

from fastapi import APIRouter

from app.agent.api.v1.endpoints.api_cache import router as api_cache_router
from app.agent.api.v1.endpoints.solo_planner import router as solo_planner_router

router = APIRouter()

router.include_router(api_cache_router, prefix="/api-cache", tags=["api-cache"])
router.include_router(solo_planner_router, prefix="/solo-planner", tags=["solo-planner"])