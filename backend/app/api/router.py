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
from app.api.v1.endpoints.client_log import router as client_log_router
from app.api.v1.endpoints.rate_limiting import router as rate_limiting_router
from app.api.v1.endpoints.rate_limiting_admin import router as rate_limiting_admin_router
from app.api.v1.endpoints.support import router as support_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(utils_router, prefix="/utils", tags=["utils"])
router.include_router(plan_router, prefix="/plan", tags=["plan"])
router.include_router(places_router, prefix="/places", tags=["places"])
router.include_router(api_cache_router, prefix="/api-cache", tags=["api-cache"])
router.include_router(client_log_router, prefix="/client-log", tags=["client-log"])
router.include_router(rate_limiting_router, prefix="/rate-limiting", tags=["rate-limiting"])
router.include_router(rate_limiting_admin_router, prefix="/rate-limiting-admin", tags=["rate-limiting-admin"])
router.include_router(support_router, prefix="/support", tags=["support"])