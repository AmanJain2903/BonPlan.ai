import requests
from typing import Dict, Annotated, Optional
from pydantic import Field
from app.core.config import settings
from datetime import datetime, timezone, timedelta
import time
from zoneinfo import ZoneInfo
import pathlib

api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED

def get_current_timestamp() -> Dict:
    try:
        current_time = int(time.time())
        return {
            "timestamp": current_time,
            "utc_string": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }
    except Exception as e:
        return {"error": f"Failed to get current time: {str(e)}"}

def convert_utc_string_to_timestamp(
    utc_string: Annotated[str, Field(description="The strict ISO 8601 UTC time string (e.g., '2026-04-05T18:30:00Z'). Must end with Z or valid UTC offset.")]) -> Dict:
    try:
        clean_string = utc_string.replace('Z', '+00:00')
        dt_object = datetime.fromisoformat(clean_string)
        
        return {
            "timestamp": int(dt_object.timestamp())
        }
    except ValueError:
        return {"error": "Invalid time format. Please provide a valid ISO 8601 string like 'YYYY-MM-DDTHH:MM:SSZ'."}
    except Exception as e:
        return {"error": f"Conversion error: {str(e)}"}

def convert_timestamp_to_utc_string(
    timestamp: Annotated[int, Field(description="The strict absolute Unix timestamp in seconds, not milliseconds.")]) -> Dict:
    try:
        dt_object = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        
        return {
            "utc_string": dt_object.isoformat().replace('+00:00', 'Z') 
        }
    except Exception as e:
        return {"error": f"Conversion error: {str(e)}"}

def convert_target_local_time_to_utc(
    local_time_string: Annotated[str, Field(description="The local time string explicitly without a 'Z' in format 'YYYY-MM-DDTHH:MM:SS' (e.g., '2026-04-25T20:00:00').")],
    timezone_id: Annotated[str, Field(description="The valid target timezone ID (e.g., 'Asia/Kolkata' or 'Europe/Paris').")]) -> Dict:
    try:
        naive_dt = datetime.strptime(local_time_string, "%Y-%m-%dT%H:%M:%S")
        target_tz = ZoneInfo(timezone_id)
        aware_dt = naive_dt.replace(tzinfo=target_tz)
        
        utc_dt = aware_dt.astimezone(timezone.utc)
        
        return {
            "original_local_time": local_time_string,
            "utc_string": utc_dt.isoformat().replace('+00:00', 'Z'),
            "utc_timestamp": int(utc_dt.timestamp())
        }
    except Exception as e:
        return {"error": f"Conversion failed. Ensure time format is 'YYYY-MM-DDTHH:MM:SS'. Error: {str(e)}"}

# Timezone API
def get_timezone(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                timestamp: Annotated[Optional[int], Field(description="The reference current or future timestamp to get the timezone at, in seconds since the Unix epoch. If not provided, only timezone name and id will be returned.", default=None)]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    if timestamp:
        url = f"https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&key={api_key}"
        no_timestamp = False
    else:
        no_timestamp = True
        timestamp = int(time.time())
        url = f"https://maps.googleapis.com/maps/api/timezone/json?location={lat},{lng}&timestamp={timestamp}&key={api_key}"
        
    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            return {"error": f"Timezone API error: {response.status_code} {response.text}"}
        data = response.json()
        totalOffset = data.get("dstOffset", None) + data.get("rawOffset", None)
        localTz = timezone(timedelta(seconds=totalOffset))
        utcDateTime = datetime.fromtimestamp(timestamp, timezone.utc)
        localDateTime = utcDateTime.astimezone(localTz)
        localDateTimeString = localDateTime.strftime("%Y-%m-%dT%H:%M:%S")

        if no_timestamp:
            output = {
                "timeZoneId": {
                    "value": data.get("timeZoneId", None),
                    "description": "The ID of the time zone."
                },
                "timeZoneName": {
                    "value": data.get("timeZoneName", None),
                    "description": "The name of the time zone."
                }
            }
            return output
        
        return {
            "dstOffset": {
                "value": data.get("dstOffset", None),
                "description": "The offset in seconds for daylight saving time."
            },
            "rawOffset": {
                "value": data.get("rawOffset", None),
                "description": "The offset in seconds from UTC time for the given location."
            },
            "timeZoneId": {
                "value": data.get("timeZoneId", None),
                "description": "The ID of the time zone."
            },
            "timeZoneName": {
                "value": data.get("timeZoneName", None),
                "description": "The name of the time zone."
            },
            "localDateTimeString": localDateTimeString
        }

    except Exception as e:
        return {"error": f"Timezone API error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_current_timestamp.__doc__ = (PROMPTS_DIR / "get_current_timestamp.md").read_text()
convert_utc_string_to_timestamp.__doc__ = (PROMPTS_DIR / "convert_utc_string_to_timestamp.md").read_text()
convert_timestamp_to_utc_string.__doc__ = (PROMPTS_DIR / "convert_timestamp_to_utc_string.md").read_text()
convert_target_local_time_to_utc.__doc__ = (PROMPTS_DIR / "convert_target_local_time_to_utc.md").read_text()
get_timezone.__doc__ = (PROMPTS_DIR / "get_timezone.md").read_text()