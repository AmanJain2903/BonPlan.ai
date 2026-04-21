from typing import Dict, Optional, Annotated, Literal, List
from pydantic import Field, BaseModel
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools.constants import GoogleFieldMasks
from app.agent.mcp_server.tools._shared import (
    Waypoint,
    normalize_waypoint,
    waypoint_validation_error,
    parse_mcp_location,
)
from app.agent.mcp_server.tools._errors import tool_error
import urllib.parse
import pathlib
from app.agent.mcp_server.tools.geocoding import get_address
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS

api_key = settings.GOOGLE_MAPS_API_KEY


# Types
travelModes = Literal["DRIVE", "WALK", "BICYCLE", "TRANSIT", "TWO_WHEELER"]

routingPreferences = Literal["TRAFFIC_AWARE", "TRAFFIC_UNAWARE", "TRAFFIC_AWARE_OPTIMAL"]

class VehicleInfo(BaseModel):
    emissionType: Literal["GASOLINE", "DIESEL", "ELECTRIC", "HYBRID"] = Field(description="The type of vehicle to use for the route.")

class RouteModifiers(BaseModel):
    avoidFerries: bool = Field(description="Whether to avoid ferries on the route.", default=False)
    avoidHighways: bool = Field(description="Whether to avoid highways on the route.", default=False)
    avoidTolls: bool = Field(description="Whether to avoid tolls on the route.", default=False)
    vehicleInfo: Optional[VehicleInfo] = Field(description="(Optional) The vehicle information to use for the route.", default=None)

# Helper Functions
async def generate_maps_app_url(origin_dict: dict, destination_dict: dict, waypoints_list: List[dict]) -> str:
    """
    Builds the official Google Maps Universal URL, preserving optimization and data types.
    Inputs are Google-shaped waypoint dicts (output of `normalize_waypoint`).
    """
    # The official base URL for Google Maps routing intents
    base_url = "https://www.google.com/maps/dir/?api=1"

    orig_query, orig_id = await parse_mcp_location(origin_dict)
    url = f"{base_url}&origin={urllib.parse.quote(orig_query)}"
    if orig_id: 
        url += f"&origin_place_id={orig_id}"

    dest_query, dest_id = await parse_mcp_location(destination_dict)
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
        q, pid = await parse_mcp_location(wp)
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

async def get_route_leg(leg: dict) -> dict:
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
            "logicalValueMeters": leg.get("distanceMeters", None)
        },
        "durationWithoutTraffic": {
            "logicalValueSeconds": int(leg["staticDuration"].rstrip('s')) if leg.get("staticDuration", None) else None
        },
        "durationWithTraffic": {
            "logicalValueSeconds": int(leg["duration"].rstrip('s')) if leg.get("duration", None) else None
        }
    }

    try:
        startAddress = (await get_address(routeLeg["startLocation"]["latitude"], routeLeg["startLocation"]["longitude"], TIMEOUTS['get_address']))["address"]
        routeLeg["startLocation"]["address"] = startAddress
    except Exception:
        routeLeg["startLocation"]["address"] = ""

    try:
        endAddress = (await get_address(routeLeg["endLocation"]["latitude"], routeLeg["endLocation"]["longitude"], TIMEOUTS['get_address']))["address"]
        routeLeg["endLocation"]["address"] = endAddress
    except Exception:
        routeLeg["endLocation"]["address"] = ""

    return routeLeg

# Routes API
async def get_route(
    origin: Annotated[Waypoint, Field(description="The origin waypoint. Provide ONE of: `address` (string), both `lat`+`lng` (floats), or `place_id` (Google Place ID).")],
    destination: Annotated[Waypoint, Field(description="The destination waypoint. Same shape as `origin`.")],
    intermediate_waypoints: Annotated[Optional[List[Waypoint]], Field(description="(Optional) Ordered list of intermediate waypoints to pass through. Same shape as `origin`.", default=None)],
    travel_mode: Annotated[travelModes, Field(description="The primary mode of travel (e.g., 'DRIVE', 'WALK', 'TRANSIT').", default="DRIVE")],
    routing_preference: Annotated[routingPreferences, Field(description="The strategy for route calculation. Determines if traffic should be considered.", default="TRAFFIC_AWARE")],
    departure_time: Annotated[Optional[str], Field(description="(Optional) The exact future departure time as a UTC ISO 8601 string.", default=None)],
    route_modifiers: Annotated[Optional[RouteModifiers], Field(description="(Optional) Avoidances and restrictions applied to the calculated route (e.g., avoidTolls).", default=None)],
    units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The unit system output format for distance.", default="IMPERIAL")],
    compute_alternative_routes: Annotated[bool, Field(description="If true, multiple route variations are computed and returned.", default=True)],
    optimize_waypoint_order: Annotated[bool, Field(description="If true, arbitrarily re-orders intermediate waypoints to find the shortest total trip time (errand mode). False enforces strict visitation order.", default=True)],
    timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_route'])],
) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    # Normalize all inputs up front so the rest of the function deals with
    # Google-shaped dicts only. Any bad waypoint short-circuits with an
    # actionable error the model can self-correct from.
    try:
        origin_google = await normalize_waypoint(origin)
    except ValueError:
        return await waypoint_validation_error("origin", origin.model_dump(exclude_none=True))

    try:
        destination_google = await normalize_waypoint(destination)
    except ValueError:
        return await waypoint_validation_error("destination", destination.model_dump(exclude_none=True))

    intermediates_google: List[dict] = []
    intermediates_flat: List[dict] = []
    if intermediate_waypoints:
        for idx, wp in enumerate(intermediate_waypoints):
            try:
                intermediates_google.append(await normalize_waypoint(wp))
            except ValueError:
                return await waypoint_validation_error(
                    f"intermediate_waypoints[{idx}]",
                    wp.model_dump(exclude_none=True),
                )
            intermediates_flat.append(wp.model_dump(exclude_none=True))

    origin_flat = origin.model_dump(exclude_none=True)
    destination_flat = destination.model_dump(exclude_none=True)

    url = f"https://routes.googleapis.com/directions/v2:computeRoutes"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["routes"]["computeRoutes"],
    }

    body = {
        "origin": origin_google,
        "destination": destination_google,
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

    if intermediates_google and travel_mode != "TRANSIT":
        body["intermediates"] = intermediates_google

    if travel_mode in ["DRIVE", "TWO_WHEELER"] and route_modifiers:
        body["routeModifiers"] = route_modifiers.model_dump(exclude_none=True)

    try:
        client = get_http_client()
        response = await client.post(url, json=body, headers=headers, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Routes API request failed.",
                fix_hint="Verify waypoints are reachable for the chosen `travel_mode` and that `departure_time` (if supplied) is in the future. 5xx is transient — retry once.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()

        routes = []
        for route in data.get("routes", []):
            r = {
                "routeLabels": route.get("routeLabels", []),
                "description": route.get("description", ""),
                "distance" : {
                    "logicalValueMeters": route.get("distanceMeters", None)
                },
                "durationWithoutTraffic" : {
                    "logicalValueSeconds": int(route.get("staticDuration", None).rstrip('s')) if route.get("staticDuration", None) else None
                },
                "durationWithTraffic" : {
                    "logicalValueSeconds": int(route.get("duration", None).rstrip('s')) if route.get("duration", None) else None
                },
                "routeLegs": [await get_route_leg(leg) for leg in route.get("legs", [])],
                "warnings": route.get("warnings", []),
                "travelAdvisory": route.get("travelAdvisory", {}),
                "mapsUrl" : await generate_maps_app_url(origin_google, destination_google, [])
            }

            if intermediates_flat:
                r["mapsUrl"] = await generate_maps_app_url(origin_google, destination_google, intermediates_google)

            if route.get("optimizedIntermediateWaypointIndex", []) != []:
                optimizedIntermediateWaypoints = [intermediates_flat[index] for index in route.get("optimizedIntermediateWaypointIndex", [])]
                optimized_google = [intermediates_google[index] for index in route.get("optimizedIntermediateWaypointIndex", [])]
                r["optimizedRoute"] = [origin_flat, *optimizedIntermediateWaypoints, destination_flat]
                r["mapsUrl"] = await generate_maps_app_url(origin_google, destination_google, optimized_google)

            if travel_mode == "TRANSIT":
                r["transitFare"] = {
                    "logicalObject" : route.get("travelAdvisory", {}).get("transitFare", {}),
                    "humanReadableValue" : route.get("localizedValues", {}).get("transitFare", {}).get("text", ""),
                }

            routes.append(r)

        if len(routes) == 0:
            return tool_error(
                "No routes found between the supplied waypoints.",
                fix_hint="Try a different `travel_mode` (e.g. DRIVE instead of TRANSIT), widen the route_modifiers (avoid fewer road types), or verify the waypoints are routable (not over water / in closed regions).",
            )

        return {"routes": routes}

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Routes API raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, simplify the route (fewer waypoints) or switch `travel_mode` and retry.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_route.__doc__ = (PROMPTS_DIR / "get_route.md").read_text()
