import requests
from typing import Dict, Optional, Annotated, Literal, List, Union
from pydantic import Field, BaseModel
from app.core.config import settings
from app.agent.mcp_server.tools.constants import GoogleFieldMasks
import urllib.parse
import pathlib
from app.agent.mcp_server.tools.geocoding import get_address

api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED

# Types
class LatLng(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0, description="The latitude of the location")
    longitude: float = Field(ge=-180.0, le=180.0, description="The longitude of the location")

class LocationWrapper(BaseModel):
    latLng: LatLng

class LocationFormat(BaseModel):
    location: LocationWrapper

class PlaceIdFormat(BaseModel):
    placeId: str = Field(description="The Google Place ID of the location")

class AddressFormat(BaseModel):
    address: str = Field(description="The raw address string of the location")

WaypointType = Union[LocationFormat, PlaceIdFormat, AddressFormat]

class WaypointFormat(BaseModel):
    waypoint: WaypointType = Field(description="The waypoint dictionary containing an address, location latLng, or placeId.")

travelModes = Literal["DRIVE", "WALK", "BICYCLE", "TRANSIT", "TWO_WHEELER"]

routingPreferences = Literal["TRAFFIC_AWARE", "TRAFFIC_UNAWARE", "TRAFFIC_AWARE_OPTIMAL"]

class VehicleInfo(BaseModel):
    emissionType: Literal["GASOLINE", "DIESEL", "ELECTRIC", "HYBRID"] = Field(description="The type of vehicle to use for the route.")

class RouteModifiers(BaseModel):
    avoidFerries: bool = Field(description="Whether to avoid ferries on the route.", default=False)
    avoidHighways: bool = Field(description="Whether to avoid highways on the route.", default=False)
    avoidTolls: bool = Field(description="Whether to avoid tolls on the route.", default=False)
    vehicleInfo: Optional[VehicleInfo] = Field(description="The vehicle information to use for the route.", default=None)

# Helper Functions
def parse_mcp_location(loc: dict) -> tuple[str, str]:
    """
    Parses WaypointType dictionary into (String_Query, Place_ID).
    Google Maps URLs require a string query even if you provide a Place ID.
    """
    if "address" in loc:
        return loc["address"], ""
    
    elif "location" in loc:
        lat = loc["location"]["latLng"]["latitude"]
        lng = loc["location"]["latLng"]["longitude"]
        return f"{lat},{lng}", ""
    
    elif "placeId" in loc:
        return "Saved Location", loc["placeId"]
        
    return "", ""

def generate_maps_app_url(origin_dict: dict, destination_dict: dict) -> str:
    """
    Builds the official Google Maps Universal URL, preserving optimization and data types.
    """
    # The official base URL for Google Maps routing intents
    base_url = "https://www.google.com/maps/dir/?api=1"

    orig_query, orig_id = parse_mcp_location(origin_dict)
    url = f"{base_url}&origin={urllib.parse.quote(orig_query)}"
    if orig_id: 
        url += f"&origin_place_id={orig_id}"

    dest_query, dest_id = parse_mcp_location(destination_dict)
    url += f"&destination={urllib.parse.quote(dest_query)}"
    if dest_id: 
        url += f"&destination_place_id={dest_id}"

    return url

# Route Matrix API
def get_route_matrix(
    origins: Annotated[List[WaypointFormat], Field(description="The list of origin route waypoint dictionaries containing an address, location latLng, or placeId and any route modifiers (e.g., avoidTolls) if needed.")],
    destinations: Annotated[List[WaypointFormat], Field(description="The list of destination route waypoint dictionaries containing an address, location latLng, or placeId.")],
    route_modifiers: Annotated[Optional[RouteModifiers], Field(description="Avoidances and restrictions applied to the calculated route (e.g., avoidTolls).", default=None)],
    travel_mode: Annotated[travelModes, Field(description="The primary mode of travel (e.g., 'DRIVE', 'WALK', 'TRANSIT').", default="DRIVE")],
    routing_preference: Annotated[routingPreferences, Field(description="The strategy for route calculation. Determines if traffic should be considered.", default="TRAFFIC_AWARE")],
    departure_time: Annotated[Optional[str], Field(description="The exact future departure time as a UTC ISO 8601 string.", default=None)],
    units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The unit system output format for distance.", default="IMPERIAL")],
) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}

    if route_modifiers:
        params["route_modifiers"] = route_modifiers.model_dump(exclude_none=True)
    
    url = f"https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["routes"]["computeRouteMatrix"],
    }

    body = {
        "origins": [waypoint.model_dump() for waypoint in origins],
        "destinations": [waypoint.model_dump() for waypoint in destinations],
        "travelMode": travel_mode,
        "units": units_system
    }
    if route_modifiers and travel_mode in ["DRIVE", "TWO_WHEELER"]:
        for origin in body["origins"]:
            origin["routeModifiers"] = route_modifiers.model_dump(exclude_none=True)

    if travel_mode in ["DRIVE", "TWO_WHEELER"] and routing_preference:
        body["routingPreference"] = routing_preference
    
    if departure_time:
        body["departureTime"] = departure_time
        if routing_preference == "TRAFFIC_UNAWARE" and travel_mode in ["DRIVE", "TWO_WHEELER"]:
            body["routingPreference"] = "TRAFFIC_AWARE"

    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
        if not response.ok:
            return {"error": f"Routes API error: {response.status_code} {response.text}"}
        data = response.json()
        
        if len(data) == 0:
            return {"error": "No route matrix found for this request"}

        routes = []
        for route in data:
            r = {
                "errorStatusMessage": route.get("status", {}).get("message", ""),
                "routeCondition": route.get("condition", ""),
                "origin": origins[route.get("originIndex", None)].model_dump().get("waypoint", {}),
                "destination": destinations[route.get("destinationIndex", None)].model_dump().get("waypoint", {}),
                "distance" : {
                    "logicalValueMeters": route.get("distanceMeters", None),
                    "humanReadableValue": route.get("localizedValues", {}).get("distance", {}).get("text", ""),
                },
                "durationWithoutTraffic" : {
                    "logicalValueSeconds": int(route["staticDuration"].rstrip('s')) if route.get("staticDuration", None) else None,
                    "humanReadableValue": route.get("localizedValues", {}).get("staticDuration", {}).get("text", ""),
                },
                "durationWithTraffic" : {
                    "logicalValueSeconds": int(route["duration"].rstrip('s')) if route.get("duration", None) else None,
                    "humanReadableValue": route.get("localizedValues", {}).get("duration", {}).get("text", ""),
                },
                "travelAdvisory": route.get("travelAdvisory", {}),
                "mapsUrl" : generate_maps_app_url(origins[route.get("originIndex", None)].model_dump().get("waypoint", {}), destinations[route.get("destinationIndex", None)].model_dump().get("waypoint", {})),
                "transitPreferenceFallbackInfo": route.get("fallbackInfo", {}),
            }
            
            if travel_mode == "TRANSIT":
                r["transitFare"] = {
                    "logicalObject" : route.get("travelAdvisory", {}).get("transitFare", {}),
                    "humanReadableValue" : route.get("localizedValues", {}).get("transitFare", {}).get("text", ""),
                }

            routes.append(r)
        
        if len(routes) == 0:
            return {"error": "No routes found for this request"}

        return {"routeMatrix": routes}

    except Exception as e:
        return {"error": f"Routes API error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_route_matrix.__doc__ = (PROMPTS_DIR / "get_route_matrix.md").read_text()