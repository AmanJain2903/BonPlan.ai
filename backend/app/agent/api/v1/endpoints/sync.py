# backend/app/agent/api/v1/endpoints/sync.py

"""
Telemetry sync endpoints for keepalive polling.
"""

import time
import platform
from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/telemetry")
async def sync_telemetry():
    """
    Endpoint for the backend service to ping, mimicking a telemetry sync.
    """
    return {
        "status": "ok",
        "service": "agent",
        "version": settings.AGENT_VERSION,
        "timestamp": time.time(),
        "platform": platform.platform()
    }