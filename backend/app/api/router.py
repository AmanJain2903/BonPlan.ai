# backend/app/api/router.py

"""
This file contains the router for the API endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router

router = APIRouter()

router.include_router(auth_router, prefix="/auth", tags=["auth"])