import requests
from typing import Dict, Annotated, Optional
from pydantic import Field
from app.core.config import settings
from datetime import datetime, timezone, timedelta
import pathlib

api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED

# Air Quality API
def get_current_air_quality(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                            lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}

    url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={api_key}"

    body = {
        "location": {
            "latitude": lat,
            "longitude": lng,
        },
        "extraComputations": ["HEALTH_RECOMMENDATIONS"],
    }
    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        if not response.ok:
            return {"error": f"Air Quality API error: {response.status_code} {response.text}"}
        data = response.json()
        return {
            "aqi": data.get("indexes", [])[0].get("aqi", None),
            "color": data.get("indexes", [])[0].get("color", None),
            "category": data.get("indexes", [])[0].get("category", None),
            "health_recommendations": data.get("healthRecommendations", None),
        }

    except Exception as e:
        return {"error": f"Air Quality API error: {str(e)}"}

def get_air_quality_forecast(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                             lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                             point_in_time: Annotated[Optional[str], Field(description="The optional precise UTC datetime to forecast the air quality at in ISO 8601 format YYYY-MM-DDTHH:MM:SSZ.", default=None)]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    if not point_in_time:
        point_in_time = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00:00Z")
    
    dt = datetime.fromisoformat(point_in_time)
    target_time = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    utc_time = datetime.now(timezone.utc)
    
    if target_time < utc_time:
        return {"error": "Point in time must be in the future"}
    
    if target_time > utc_time + timedelta(hours=96):
        return {"error": "Point in time must be within 96 hours from now"}

    url = f"https://airquality.googleapis.com/v1/forecast:lookup?key={api_key}"
    body = {
        "location": {
            "latitude": lat,
            "longitude": lng,
        },
        "dateTime": point_in_time,
        "extraComputations": ["HEALTH_RECOMMENDATIONS"],
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        if not response.ok:
            return {"error": f"Air Quality API error: {response.status_code} {response.text}"}
        data = response.json()

        return{
            "dateTime": data.get("hourlyForecasts", [])[0].get("dateTime", None),
            "aqi": data.get("hourlyForecasts", [])[0].get("indexes", [])[0].get("aqi", None) if data.get("hourlyForecasts", [])[0].get("indexes", []) else None,
            "color": data.get("hourlyForecasts", [])[0].get("indexes", [])[0].get("color", None) if data.get("hourlyForecasts", [])[0].get("indexes", []) else None,
            "category": data.get("hourlyForecasts", [])[0].get("indexes", [])[0].get("category", None) if data.get("hourlyForecasts", [])[0].get("indexes", []) else None,
            "health_recommendations": data.get("hourlyForecasts", [])[0].get("healthRecommendations", None),
        }

    except Exception as e:
        return {"error": f"Air Quality API error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_current_air_quality.__doc__ = (PROMPTS_DIR / "get_current_air_quality.md").read_text()
get_air_quality_forecast.__doc__ = (PROMPTS_DIR / "get_air_quality_forecast.md").read_text()