# backend/app/api/router.py

"""
This file contains the router for the API endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.utils import router as utils_router
from app.api.v1.endpoints.plan import router as plan_router
from app.api.v1.endpoints.places import router as places_router
from app.api.v1.endpoints.api_cache import router as api_cache_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(utils_router, prefix="/utils", tags=["utils"])
router.include_router(plan_router, prefix="/plan", tags=["plan"])
router.include_router(places_router, prefix="/places", tags=["places"])
router.include_router(api_cache_router, prefix="/api-cache", tags=["api-cache"])