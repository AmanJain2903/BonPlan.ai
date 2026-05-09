# backend/app/api/v1/endpoints/sync.py

"""
Telemetry sync endpoints for keepalive polling.
"""

import time
import platform
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.api_route("/telemetry", methods=["GET", "HEAD"])
async def sync_telemetry():
    """
    Endpoint for the agent service to ping, mimicking a telemetry sync.
    """
    return {
        "status": "ok",
        "service": "backend",
        "version": settings.PROJECT_VERSION,
        "timestamp": time.time(),
        "platform": platform.platform()
    }
