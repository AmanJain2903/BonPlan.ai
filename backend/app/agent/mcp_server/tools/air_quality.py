from typing import Dict, Annotated, Optional
from pydantic import Field
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools._errors import tool_error
from datetime import datetime, timezone, timedelta
import pathlib
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS

api_key = settings.GOOGLE_MAPS_API_KEY

# Air Quality API
async def get_current_air_quality(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                            lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                            timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout.", default=TIMEOUTS['get_current_air_quality'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without air-quality data.",
        )

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
        client = get_http_client()
        response = await client.post(url, json=body, headers=headers, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Air Quality API request failed.",
                fix_hint="Verify lat/lng are within valid ranges and that the location has AQ coverage. If status is 5xx, retry once; otherwise proceed without AQI data.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()

        indexes = data.get("indexes") or []
        if not indexes:
            return tool_error(
                "No AQI index available for this location.",
                fix_hint="Google returned no AQ indexes for this lat/lng. Either the location has no coverage or the query was invalid. Proceed without AQI data, or try a nearby coordinate.",
            )

        primary = indexes[0]
        return {
            "aqi": primary.get("aqi", None),
            "color": primary.get("color", None),
            "category": primary.get("category", None),
            "health_recommendations": data.get("healthRecommendations", None),
        }

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Air Quality API raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without AQI data.",
            extra={"exception": str(e)},
        )

async def get_air_quality_forecast(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                             lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                             point_in_time: Annotated[Optional[str], Field(description="(Optional) The precise UTC datetime to forecast the air quality at in ISO 8601 format YYYY-MM-DDTHH:MM:SSZ.", default=None)],
                             timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout.", default=TIMEOUTS['get_air_quality_forecast'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without air-quality data.",
        )

    if not point_in_time:
        point_in_time = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00:00Z")

    try:
        dt = datetime.fromisoformat(point_in_time.replace('Z', '+00:00'))
    except Exception:
        return tool_error(
            "`point_in_time` could not be parsed as ISO 8601.",
            fix_hint="Retry with `point_in_time` in the exact form YYYY-MM-DDTHH:MM:SSZ, e.g. '2026-04-25T20:00:00Z'.",
            extra={"received": point_in_time},
        )
    target_time = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    utc_time = datetime.now(timezone.utc)

    if target_time < utc_time:
        return tool_error(
            "`point_in_time` must be in the future.",
            fix_hint="Retry with `point_in_time` set to a UTC timestamp strictly after the current time and within the next 96 hours.",
            extra={"received": point_in_time, "now_utc": utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")},
        )

    if target_time > utc_time + timedelta(hours=96):
        return tool_error(
            "`point_in_time` must be within 96 hours from now.",
            fix_hint="Retry with `point_in_time` no more than 96 hours in the future. For trips further out, use climatology heuristics instead of forecast data.",
            extra={"received": point_in_time},
        )

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
        client = get_http_client()
        response = await client.post(url, json=body, headers=headers, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Air Quality forecast request failed.",
                fix_hint="Verify lat/lng are within valid ranges and `point_in_time` is within the next 96 hours. If status is 5xx, retry once; otherwise proceed without forecast data.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()

        hourly = data.get("hourlyForecasts") or []
        if not hourly:
            return tool_error(
                "No AQI forecast available for this location/time.",
                fix_hint="Google returned no forecast hours for this request. Either the location has no coverage or the timestamp was outside the valid window. Proceed without forecast data.",
            )

        first_hour = hourly[0]
        indexes = first_hour.get("indexes") or []
        primary = indexes[0] if indexes else {}

        return {
            "dateTime": first_hour.get("dateTime", None),
            "aqi": primary.get("aqi", None),
            "color": primary.get("color", None),
            "category": primary.get("category", None),
            "health_recommendations": first_hour.get("healthRecommendations", None),
        }

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Air Quality forecast raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without forecast data.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_current_air_quality.__doc__ = (PROMPTS_DIR / "get_current_air_quality.md").read_text()
get_air_quality_forecast.__doc__ = (PROMPTS_DIR / "get_air_quality_forecast.md").read_text()
