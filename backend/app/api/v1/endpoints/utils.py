# backend/app/api/v1/endpoints/utils.py

"""

This file contains the utility endpoints for the v1 version of the API.
"""

from fastapi import APIRouter

from app.agent.mcp_server.tools.timezone import get_timezone as get_timezone_tool

from app.logging import get_api_logger

logger = get_api_logger("api.utils")


router = APIRouter()

"""
Get timezone endpoint
"""
@router.post("/get-timezone", response_model=dict)
async def get_timezone(lat: float, lng: float):
    try:
        timezoneInfo = await get_timezone_tool(lat, lng, timestamp=None, timeout_seconds=None)
        if timezoneInfo.get("timeZoneId", {}).get("value", ""):
            return {"timezoneId": timezoneInfo.get("timeZoneId").get("value")}
        return {"timezoneId": "UTC"}
    except Exception as e:
        logger.error("Failed to get timezone", lat=lat, lng=lng, error=str(e))
        return {"timezoneId": "UTC"}
        

    
