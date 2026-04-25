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
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.logging import get_mcp_logger
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_get_route_matrix_sku

logger = get_mcp_logger("tools.route_matrix")

api_key = settings.GOOGLE_MAPS_API_KEY


# Types
travelModes = Literal["DRIVE", "WALK", "BICYCLE", "TRANSIT"]

routingPreferences = Literal["TRAFFIC_AWARE", "TRAFFIC_UNAWARE", "TRAFFIC_AWARE_OPTIMAL"]

class VehicleInfo(BaseModel):
    emissionType: Literal["GASOLINE", "DIESEL", "ELECTRIC", "HYBRID"] = Field(description="The type of vehicle to use for the route.")

class RouteModifiers(BaseModel):
    avoidFerries: bool = Field(description="Whether to avoid ferries on the route.", default=False)
    avoidHighways: bool = Field(description="Whether to avoid highways on the route.", default=False)
    avoidTolls: bool = Field(description="Whether to avoid tolls on the route.", default=False)
    vehicleInfo: Optional[VehicleInfo] = Field(description="(Optional) The vehicle information to use for the route.", default=None)

# Helper Functions
async def generate_maps_app_url(origin_dict: dict, destination_dict: dict) -> str:
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

    return url

# Route Matrix API
async def get_route_matrix(
    origins: Annotated[List[Waypoint], Field(description="List of origin waypoints. Each item must provide ONE of: `address` (string), both `lat`+`lng` (floats), or `place_id` (Google Place ID).")],
    destinations: Annotated[List[Waypoint], Field(description="List of destination waypoints. Same shape as `origins`.")],
    route_modifiers: Annotated[Optional[RouteModifiers], Field(description="(Optional) Avoidances and restrictions applied to the calculated route (e.g., avoidTolls).", default=None)],
    travel_mode: Annotated[travelModes, Field(description="The primary mode of travel (e.g., 'DRIVE', 'WALK', 'TRANSIT').", default="DRIVE")],
    routing_preference: Annotated[routingPreferences, Field(description="The strategy for route calculation. Determines if traffic should be considered.", default="TRAFFIC_AWARE")],
    departure_time: Annotated[Optional[str], Field(description="(Optional) The exact future departure time as a UTC ISO 8601 string.", default=None)],
    units_system: Annotated[Literal["IMPERIAL", "METRIC"], Field(description="The unit system output format for distance.", default="IMPERIAL")],
    timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_route_matrix'])],
) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    if not origins or not destinations:
        return tool_error(
            "Both `origins` and `destinations` must be non-empty lists.",
            fix_hint="Retry the call with at least one origin and one destination.",
        )

    # Normalize all origins and destinations up front. Each bad entry is
    # reported with an actionable error keyed by its index.
    origins_google: List[dict] = []
    origins_flat: List[dict] = []
    for idx, wp in enumerate(origins):
        try:
            origins_google.append(await normalize_waypoint(wp))
        except ValueError:
            return await waypoint_validation_error(
                f"origins[{idx}]", wp.model_dump(exclude_none=True)
            )
        origins_flat.append(wp.model_dump(exclude_none=True))

    destinations_google: List[dict] = []
    destinations_flat: List[dict] = []
    for idx, wp in enumerate(destinations):
        try:
            destinations_google.append(await normalize_waypoint(wp))
        except ValueError:
            return await waypoint_validation_error(
                f"destinations[{idx}]", wp.model_dump(exclude_none=True)
            )
        destinations_flat.append(wp.model_dump(exclude_none=True))

    # Context-aware SKU: branches on routing_preference.
    resolved_sku = resolve_get_route_matrix_sku(routing_preference=routing_preference)
    try:
        await get_rate_limiter().consume(resolved_sku)
    except RateLimitExceeded as exc:
        return tool_error(
            f"Monthly quota exhausted for SKU '{exc.sku}'.",
            fix_hint=f"Do not retry this route-matrix call. Retry after {exc.retry_after_seconds}s, or reduce origin/destination counts.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

    url = f"https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["routes"]["computeRouteMatrix"],
    }

    body = {
        "origins": [{"waypoint": wp} for wp in origins_google],
        "destinations": [{"waypoint": wp} for wp in destinations_google],
        "travelMode": travel_mode,
        "units": units_system,
    }
    if route_modifiers and travel_mode in ["DRIVE"]:
        modifiers_payload = route_modifiers.model_dump(exclude_none=True)
        for origin_entry in body["origins"]:
            origin_entry["routeModifiers"] = modifiers_payload

    if travel_mode in ["DRIVE"] and routing_preference:
        body["routingPreference"] = routing_preference
    
    if departure_time:
        body["departureTime"] = departure_time
        if routing_preference == "TRAFFIC_UNAWARE" and travel_mode in ["DRIVE"]:
            body["routingPreference"] = "TRAFFIC_AWARE"

    try:
        client = get_http_client()
        response = await client.post(url, json=body, headers=headers, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Route Matrix API request failed.",
                fix_hint="Verify waypoints are routable for the chosen `travel_mode`. Limit the combined origins * destinations count (Google allows up to 625). 5xx is transient — retry once.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()

        if len(data) == 0:
            return tool_error(
                "Empty route matrix returned.",
                fix_hint="Try a different `travel_mode` or verify none of the origin/destination pairs are unreachable (e.g. crossing oceans for DRIVE).",
            )

        routes = []
        for route in data:
            origin_index = route.get("originIndex", None)
            destination_index = route.get("destinationIndex", None)

            origin_flat = (
                origins_flat[origin_index]
                if origin_index is not None and 0 <= origin_index < len(origins_flat)
                else {}
            )
            destination_flat = (
                destinations_flat[destination_index]
                if destination_index is not None
                and 0 <= destination_index < len(destinations_flat)
                else {}
            )
            origin_google = (
                origins_google[origin_index]
                if origin_index is not None and 0 <= origin_index < len(origins_google)
                else {}
            )
            destination_google = (
                destinations_google[destination_index]
                if destination_index is not None
                and 0 <= destination_index < len(destinations_google)
                else {}
            )

            r = {
                "errorStatusMessage": route.get("status", {}).get("message", ""),
                "routeCondition": route.get("condition", ""),
                "originIndex": origin_index,
                "destinationIndex": destination_index,
                "origin": origin_flat,
                "destination": destination_flat,
                "distanceMeters": route.get("distanceMeters"),
                "durationWithoutTrafficSeconds": int(route["staticDuration"].rstrip('s')) if route.get("staticDuration") else None,
                "durationWithTrafficSeconds": int(route["duration"].rstrip('s')) if route.get("duration") else None,
                "mapsUrl": await generate_maps_app_url(origin_google, destination_google),
            }

            if travel_mode == "TRANSIT":
                r["transitFare"] = route.get("localizedValues", {}).get("transitFare", {}).get("text", "")

            routes.append(r)

        if len(routes) == 0:
            return tool_error(
                "No routes found between the supplied waypoint pairs.",
                fix_hint="Try fewer waypoints, a different `travel_mode`, or verify reachability between every origin/destination pair.",
            )

        return {"routeMatrix": routes}

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Route Matrix API raised an unexpected error.",
            fix_hint="Retry once. If it fails again, reduce the origin/destination count and try again.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_route_matrix.__doc__ = (PROMPTS_DIR / "get_route_matrix.md").read_text()
