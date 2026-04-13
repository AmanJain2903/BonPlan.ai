import requests
from typing import Dict, Optional, Annotated, Literal
from pydantic import Field
from app.core.config import settings
from datetime import datetime, timezone, timedelta
import pathlib

api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED

# Weather API
def get_current_weather(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                        lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                        units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The preferred units system for the weather data.", default="IMPERIAL")]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}

    url = f"https://weather.googleapis.com/v1/currentConditions:lookup?key={api_key}&location.latitude={lat}&location.longitude={lng}&unitsSystem={units_system}"

    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            return {"error": f"Weather API error: {response.status_code} {response.text}"}
        data = response.json()

        return {
            "isDaytime": data.get("isDaytime", None),
            "weatherCondition" : {
                "description": data.get("weatherCondition", {}).get("description", {}).get("text", None),
                "type": data.get("weatherCondition", {}).get("type", None),
                "iconURI": data.get("weatherCondition", {}).get("iconBaseUri", None),
            },
            "currentTemperature": {
                "value": data.get("temperature", {}).get("degrees", None),
                "unit": data.get("temperature", {}).get("unit", None),
            },
            "maxTemperature": {
                "value": data.get("currentConditionsHistory", {}).get("maxTemperature", {}).get("degrees", None),
                "unit": data.get("currentConditionsHistory", {}).get("maxTemperature", {}).get("unit", None),
            },
            "minTemperature": {
                "value": data.get("currentConditionsHistory", {}).get("minTemperature", {}).get("degrees", None),
                "unit": data.get("currentConditionsHistory", {}).get("minTemperature", {}).get("unit", None),
            },
            "feelsLike": {
                "value": data.get("feelsLikeTemperature", {}).get("degrees", None),
                "unit": data.get("feelsLikeTemperature", {}).get("unit", None),
            },
            "precipitation": {
                "type": data.get("precipitation", {}).get("probability", {}).get("type", None),
                "probability": data.get("precipitation", {}).get("probability", {}).get("percent", None),
            },
            "thunderstormProbability": data.get("thunderstormProbability", None),
            "visibility": {
                "distance": data.get("visibility", {}).get("distance", None),
                "unit": data.get("visibility", {}).get("unit", None),
            },
        }

    except Exception as e:
        return {"error": f"Weather API error: {str(e)}"}

def get_daily_forecast(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                       lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                       units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The preferred units system for the weather data.", default="IMPERIAL")],
                       days: Annotated[int, Field(ge=1, le=10, description="The number of days to forecast.", default=10)]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}

    url = f"https://weather.googleapis.com/v1/forecast/days:lookup?key={api_key}&location.latitude={lat}&location.longitude={lng}&unitsSystem={units_system}&days={days}&pageSize=10"

    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            return {"error": f"Weather API error: {response.status_code} {response.text}"}
        data = response.json()

        output = {
        }

        for day in data.get("forecastDays", []):
            date_time_string = day.get("interval", {}).get("startTime", None)
            output[date_time_string] = {
                "maxTemperature": {
                    "value": day.get("maxTemperature", {}).get("degrees", None),
                    "unit": day.get("maxTemperature", {}).get("unit", None),
                },
                "minTemperature": {
                    "value": day.get("minTemperature", {}).get("degrees", None),
                    "unit": day.get("minTemperature", {}).get("unit", None),
                },
                "feelsLikeMaxTemperature": {
                    "value": day.get("feelsLikeMaxTemperature", {}).get("degrees", None),
                    "unit": day.get("feelsLikeMaxTemperature", {}).get("unit", None),
                },
                "feelsLikeMinTemperature": {
                    "value": day.get("feelsLikeMinTemperature", {}).get("degrees", None),
                    "unit": day.get("feelsLikeMinTemperature", {}).get("unit", None),
                },
                "dayTimeForecast" : {
                    "weatherCondition" : {
                        "description": day.get("daytimeForecast", {}).get("weatherCondition", {}).get("description", {}).get("text", None),
                        "type": day.get("daytimeForecast", {}).get("weatherCondition", {}).get("type", None),
                        "iconURI": day.get("daytimeForecast", {}).get("weatherCondition", {}).get("iconBaseUri", None),
                    },
                    "precipitation": {
                        "type": day.get("daytimeForecast", {}).get("precipitation", {}).get("probability", {}).get("type", None),
                        "probability": day.get("daytimeForecast", {}).get("precipitation", {}).get("probability", {}).get("percent", None),
                    },
                    "thunderstormProbability": day.get("daytimeForecast", {}).get("thunderstormProbability", None),
                },
                "nightTimeForecast" : {
                    "weatherCondition" : {
                        "description": day.get("nighttimeForecast", {}).get("weatherCondition", {}).get("description", {}).get("text", None),
                        "type": day.get("nighttimeForecast", {}).get("weatherCondition", {}).get("type", None),
                        "iconURI": day.get("nighttimeForecast", {}).get("weatherCondition", {}).get("iconBaseUri", None),
                    },
                    "precipitation": {
                        "type": day.get("nighttimeForecast", {}).get("precipitation", {}).get("probability", {}).get("type", None),
                        "probability": day.get("nighttimeForecast", {}).get("precipitation", {}).get("probability", {}).get("percent", None),
                    },
                    "thunderstormProbability": day.get("nighttimeForecast", {}).get("thunderstormProbability", None),
                },
            }
        
        return {
            "timeZone": data.get("timeZone", {}).get("id", None),
            "forecastDays": output,
        }

    except Exception as e:
        return {"error": f"Weather API error: {str(e)}"}

def get_hourly_forecast(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")], 
                        lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")], 
                        units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The preferred units system for the weather data.", default="IMPERIAL")], 
                        hours: Annotated[int, Field(ge=1, le=24, description="The total number of hours to forecast (max 24).", default=24)]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}

    url = f"https://weather.googleapis.com/v1/forecast/hours:lookup?key={api_key}&location.latitude={lat}&location.longitude={lng}&unitsSystem={units_system}&hours={hours}"

    try:
        response = requests.get(url, timeout=5)
        if not response.ok:
            return {"error": f"Weather API error: {response.status_code} {response.text}"}
        data = response.json()

        output = {
        }

        for hour in data.get("forecastHours", []):
            date_time_string = hour.get("interval", {}).get("startTime", None)
            output[date_time_string] = {
                "isDaytime": hour.get("isDaytime", None),
                "temperature": {
                    "value": hour.get("temperature", {}).get("degrees", None),
                    "unit": hour.get("temperature", {}).get("unit", None),
                },
                "feelsLike": {
                    "value": hour.get("feelsLikeTemperature", {}).get("degrees", None),
                    "unit": hour.get("feelsLikeTemperature", {}).get("unit", None),
                },
                "weatherCondition" : {
                    "description": hour.get("weatherCondition", {}).get("description", {}).get("text", None),
                    "type": hour.get("weatherCondition", {}).get("type", None),
                    "iconURI": hour.get("weatherCondition", {}).get("iconBaseUri", None),
                },
                "precipitation": {
                    "type": hour.get("precipitation", {}).get("probability", {}).get("type", None),
                    "probability": hour.get("precipitation", {}).get("probability", {}).get("percent", None),
                },
                "thunderstormProbability": hour.get("thunderstormProbability", None),
                "visibility": {
                    "distance": hour.get("visibility", {}).get("distance", None),
                    "unit": hour.get("visibility", {}).get("unit", None),
                },
            }
        
        return {
            "timeZone": data.get("timeZone", {}).get("id", None),
            "forecastHours": output,
        }

    except Exception as e:
        return {"error": f"Weather API error: {str(e)}"}

# FOR FUTURE USE
# def get_weather_alerts(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The latitude of the location")],
#                         lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The longitude of the location")]) -> Dict:
#     """
#     Get the weather alerts for a location.
#     Arguments:
#         lat: The latitude of the location
#         lng: The longitude of the location
#         NO OTHER ARGUMENTS ARE ALLOWED
#     """
#     if not api_key:
#         return {"error": "Google API key not configured"}

#     url = f"https://weather.googleapis.com/v1/publicAlerts:lookup?key={api_key}&location.latitude={lat}&location.longitude={lng}"
#     try:
#         response = requests.get(url, timeout=5)
#         if not response.ok:
#             return {"error": f"Weather API error: {response.status_code} {response.text}"}
#         data = response.json()

#         return data

#         return {"error": f"Weather API error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_current_weather.__doc__ = (PROMPTS_DIR / "get_current_weather.md").read_text()
get_daily_forecast.__doc__ = (PROMPTS_DIR / "get_daily_forecast.md").read_text()
get_hourly_forecast.__doc__ = (PROMPTS_DIR / "get_hourly_forecast.md").read_text()

