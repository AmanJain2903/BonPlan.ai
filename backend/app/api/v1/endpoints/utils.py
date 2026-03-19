# backend/app/api/v1/endpoints/utils.py

"""
This file contains the utility endpoints for the v1 version of the API.
"""

from app.core.config import settings

from fastapi import HTTPException, Request, APIRouter, Depends

from timezonefinder import TimezoneFinder


router = APIRouter()

tf = TimezoneFinder()

"""
Helper functions
"""
def get_timezone_id(lat: float, lng: float):
    try:
        tfId = tf.timezone_at(lat=lat, lng=lng)
        if tfId:
            return {"timezoneId": tfId}
        return {"timezoneId": "UTC"}
    except Exception as e:
        return {"timezoneId": "UTC"}


"""
Get timezone endpoint
"""
@router.post("/get-timezone", response_model=dict)
def get_timezone(lat: float, lng: float):
    return get_timezone_id(lat, lng)

    


