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
def getOptimizedRoute(optimized_intermediate_waypoint_index: List[int], origin: WaypointType, destination: WaypointType, intermediate_waypoints: List[WaypointType]) -> List[WaypointType]:
    route = []
    route.append(origin)
    for index in optimized_intermediate_waypoint_index:
        route.append(intermediate_waypoints[index])
    route.append(destination)
    return route

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

def generate_maps_app_url(origin_dict: dict, destination_dict: dict, waypoints_list: List[dict]) -> str:
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

    # Return early if there are no intermediate stops
    if not waypoints_list or len(waypoints_list) == 0:
        return url

    wp_queries = []
    wp_ids = []
    has_any_place_id = False

    for wp in waypoints_list:
        q, pid = parse_mcp_location(wp)
        wp_queries.append(urllib.parse.quote(q))
        wp_ids.append(pid) # Appends an empty string if it's an address/coordinate
        if pid: 
            has_any_place_id = True

    # Join the queries with the Google Maps pipe character '|'
    url += "&waypoints=" + "|".join(wp_queries)

    if has_any_place_id:
        # Google requires the pipes to match the waypoints, e.g., "||ChIJ...|"
        url += "&waypoint_place_ids=" + "|".join(wp_ids)

    return url

def get_route_leg(leg: dict) -> dict:
    routeLeg = {
        "startLocation": {
            "latitude": leg.get("startLocation", {}).get("latLng", {}).get("latitude", None),
            "longitude": leg.get("startLocation", {}).get("latLng", {}).get("longitude", None)
        },
        "endLocation": {
            "latitude": leg.get("endLocation", {}).get("latLng", {}).get("latitude", None),
            "longitude": leg.get("endLocation", {}).get("latLng", {}).get("longitude", None)
        },
        "distance": {
            "logicalValueMeters": leg.get("distanceMeters", None),
            "humanReadableValue": leg.get("localizedValues", {}).get("distance", {}).get("text", ""),
        },
        "durationWithoutTraffic": {
            "logicalValueSeconds": int(leg["staticDuration"].rstrip('s')) if leg.get("staticDuration", None) else None,
            "humanReadableValue": leg.get("localizedValues", {}).get("staticDuration", {}).get("text", ""),
        },
        "durationWithTraffic": {
            "logicalValueSeconds": int(leg["duration"].rstrip('s')) if leg.get("duration", None) else None,
            "humanReadableValue": leg.get("localizedValues", {}).get("duration", {}).get("text", ""),
        },
        "polyline": leg.get("polyline", {}),
    }

    try:
        startAddress = get_address(routeLeg["startLocation"]["latitude"], routeLeg["startLocation"]["longitude"])["address"]
        routeLeg["startLocation"]["address"] = startAddress
    except Exception as e:
        routeLeg["startLocation"]["address"] = ""

    try:
        endAddress = get_address(routeLeg["endLocation"]["latitude"], routeLeg["endLocation"]["longitude"])["address"]
        routeLeg["endLocation"]["address"] = endAddress
    except Exception as e:
        routeLeg["endLocation"]["address"] = ""

    return routeLeg

# Routes API
def get_route(
    origin: Annotated[WaypointType, Field(description="The origin route waypoint dictionary containing an address, location latLng, or placeId.")],
    destination: Annotated[WaypointType, Field(description="The destination route waypoint dictionary.")],
    intermediate_waypoints: Annotated[Optional[List[WaypointType]], Field(description="The optional list of intermediate route waypoint dictionaries to pass through.", default=None)],
    travel_mode: Annotated[travelModes, Field(description="The primary mode of travel (e.g., 'DRIVE', 'WALK', 'TRANSIT').", default="DRIVE")],
    routing_preference: Annotated[routingPreferences, Field(description="The strategy for route calculation. Determines if traffic should be considered.", default="TRAFFIC_AWARE")],
    departure_time: Annotated[Optional[str], Field(description="The exact future departure time as a UTC ISO 8601 string.", default=None)],
    route_modifiers: Annotated[Optional[RouteModifiers], Field(description="Avoidances and restrictions applied to the calculated route (e.g., avoidTolls).", default=None)],
    units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The unit system output format for distance.", default="IMPERIAL")],
    compute_alternative_routes: Annotated[bool, Field(description="If true, multiple route variations are computed and returned.", default=True)],
    optimize_waypoint_order: Annotated[bool, Field(description="If true, arbitrarily re-orders intermediate waypoints to find the shortest total trip time (errand mode). False enforces strict visitation order.", default=True)],
) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}

    if intermediate_waypoints:
        params["intermediate_waypoints"] = [waypoint.model_dump() for waypoint in intermediate_waypoints]
    
    if route_modifiers:
        params["route_modifiers"] = route_modifiers.model_dump(exclude_none=True)
    
    url = f"https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["routes"]["computeRoutes"],
    }

    body = {
        "origin": origin.model_dump(),
        "destination": destination.model_dump(),
        "travelMode": travel_mode,
        "units": units_system,
        "computeAlternativeRoutes": compute_alternative_routes,
        "optimizeWaypointOrder": optimize_waypoint_order,
    }
    if travel_mode in ["DRIVE", "TWO_WHEELER"] and routing_preference:
        body["routingPreference"] = routing_preference
    
    if departure_time:
        body["departureTime"] = departure_time
        if routing_preference == "TRAFFIC_UNAWARE" and travel_mode in ["DRIVE", "TWO_WHEELER"]:
            body["routingPreference"] = "TRAFFIC_AWARE"

    if intermediate_waypoints and travel_mode != "TRANSIT":
        body["intermediates"] = [waypoint.model_dump() for waypoint in intermediate_waypoints]
    
    if travel_mode in ["DRIVE", "TWO_WHEELER"] and route_modifiers:
        body["routeModifiers"] = route_modifiers.model_dump(exclude_none=True)

    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        if not response.ok:
            return {"error": f"Routes API error: {response.status_code} {response.text}"}
        data = response.json()

        routes = []
        for route in data.get("routes", []):
            r = {
                "routeLabels": route.get("routeLabels", []),
                "description": route.get("description", ""),
                "distance" : {
                    "logicalValueMeters": route.get("distanceMeters", None),
                    "humanReadableValue": route.get("localizedValues", {}).get("distance", {}).get("text", ""),
                },
                "durationWithoutTraffic" : {
                    "logicalValueSeconds": int(route.get("staticDuration", None).rstrip('s')) if route.get("staticDuration", None) else None,
                    "humanReadableValue": route.get("localizedValues", {}).get("staticDuration", {}).get("text", ""),
                },
                "durationWithTraffic" : {
                    "logicalValueSeconds": int(route.get("duration", None).rstrip('s')) if route.get("duration", None) else None,
                    "humanReadableValue": route.get("localizedValues", {}).get("duration", {}).get("text", ""),
                },
                "routeLegs": [get_route_leg(leg) for leg in route.get("legs", [])],
                "warnings": route.get("warnings", []),
                "travelAdvisory": route.get("travelAdvisory", {}),
                "optimizedIntermediateWaypointIndex": route.get("optimizedIntermediateWaypointIndex", []),
                "polyline" : route.get("polyline", {}),
                "routeToken": route.get("routeToken", None),
                "mapsUrl" : generate_maps_app_url(origin.model_dump(), destination.model_dump(), [])
            }

            if intermediate_waypoints:
                r["intermediateWaypoints"] = [waypoint.model_dump() for waypoint in intermediate_waypoints]
                r["mapsUrl"] = generate_maps_app_url(origin.model_dump(), destination.model_dump(), r["intermediateWaypoints"])
            
            if r["optimizedIntermediateWaypointIndex"] != []:
                r["optimizedIntermediateWaypoints"] = [intermediate_waypoints[index].model_dump() for index in r["optimizedIntermediateWaypointIndex"]]
                raw_optimized_route = getOptimizedRoute(r["optimizedIntermediateWaypointIndex"], origin, destination, intermediate_waypoints)
                r["optimizedRoute"] = [wp.model_dump() for wp in raw_optimized_route]
                r["mapsUrl"] = generate_maps_app_url(origin.model_dump(), destination.model_dump(), r["optimizedIntermediateWaypoints"])
            
            if travel_mode == "TRANSIT":
                r["transitFare"] = {
                    "logicalObject" : route.get("travelAdvisory", {}).get("transitFare", {}),
                    "humanReadableValue" : route.get("localizedValues", {}).get("transitFare", {}).get("text", ""),
                }

            routes.append(r)
        
        if len(routes) == 0:
            return {"error": "No routes found for this request"}

        return {"routes": routes}

    except Exception as e:
        return {"error": f"Routes API error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_route.__doc__ = (PROMPTS_DIR / "get_route.md").read_text()