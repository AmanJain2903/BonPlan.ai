from typing import Dict, Annotated, Tuple, Optional, List
from pydantic import Field, BaseModel
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools._errors import tool_error
import pathlib
from app.agent.api.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
import math
import itertools
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import SKU


from app.logging import get_mcp_logger
logger = get_mcp_logger("tools.geocoding")
api_key = settings.GOOGLE_MAPS_API_KEY

class Location(BaseModel):
    addressOrName: Annotated[str, Field(description="The address or name of the location.")]
    lat: Annotated[Optional[float], Field(description="(Optional) The latitude of the location.", default=None)]
    lng: Annotated[Optional[float], Field(description="(Optional) The longitude of the location.", default=None)]

async def haversineDistance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    lat1, lon1 = point1
    lat2, lon2 = point2
    R = 6371 # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Geocoding API
async def get_coordinates(address: Annotated[str, Field(description="The formal physical address or general city name to convert to absolute lat/lng coordinates.")],
                          timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_coordinates'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    if not address:
        return tool_error(
            "`address` is required.",
            fix_hint="Retry with a non-empty address or city name.",
        )

    cache_key = await generate_cache_key("get_coordinates", {"address": address.lower().strip()})
    cache_value = await retrieve_api_cache(cache_key, expires_in=31)

    # Rate-limit: skip counting on cache hit so repeated requests for the
    # same address don't burn the monthly Geocoding quota.
    try:
        await get_rate_limiter().consume(SKU["geocoding"], cache_hit=bool(cache_value))
    except RateLimitExceeded as exc:
        return tool_error(
            "Monthly Geocoding SKU quota exhausted.",
            fix_hint=f"Do not retry. Skip geocoding for this address. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

    try:
        if cache_value:
            data = cache_value
        else:
            client = get_http_client()
            response = await client.get(url, params=params, timeout=timeout_seconds)
            if response.status_code >= 400:
                return tool_error(
                    "Geocoding failed upstream.",
                    fix_hint="5xx responses are transient — retry once. 4xx typically means the address was invalid; simplify it (try just the city and country) and retry.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            data = response.json()
            if data["status"] != "OK":
                return tool_error(
                    f"Geocoding returned status '{data.get('status', 'Unknown')}'.",
                    fix_hint="Simplify the address (e.g. 'Eiffel Tower, Paris' instead of a full street address), or fall back to a well-known landmark name and retry.",
                    extra={"upstream_status": data.get("status"), "error_message": data.get("error_message")},
                )
            await insert_api_cache(cache_key, data)


        results = data.get("results") or []
        if not results or not results[0].get("geometry", {}).get("location"):
            return tool_error(
                "Geocoding returned no results.",
                fix_hint="Simplify the query and retry (e.g. just the city and country), or use a landmark name.",
            )

        result = results[0]
        return {
            "address": result.get("formatted_address", ""),
            "lat": result.get("geometry", {}).get("location", {}).get("lat", None),
            "lng": result.get("geometry", {}).get("location", {}).get("lng", None),
            "place_id": result.get("place_id", None)
        }

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Geocoding raised an unexpected error.",
            fix_hint="Retry once. If it fails again, use a different address phrasing.",
            extra={"exception": str(e)},
        )

async def get_address(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")],
                timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_address'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    # Use `is None` so the legitimate coordinate 0.0 isn't rejected as falsy.
    if lat is None or lng is None:
        return tool_error(
            "Both `lat` and `lng` are required.",
            fix_hint="Retry with both lat and lng as floats. Use 0.0 explicitly if the coordinate really is zero.",
        )

    cache_key = await generate_cache_key("get_address", {"lat": lat, "lng": lng})
    cache_value = await retrieve_api_cache(cache_key, expires_in=31)

    # Rate-limit: shared "geocoding" SKU. Skip on cache hit.
    try:
        await get_rate_limiter().consume(SKU["geocoding"], cache_hit=bool(cache_value))
    except RateLimitExceeded as exc:
        return tool_error(
            "Monthly Geocoding SKU quota exhausted.",
            fix_hint=f"Do not retry. Skip reverse-geocoding. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": api_key
    }

    try:
        if cache_value:
            data = cache_value
        else:
            client = get_http_client()
            response = await client.get(url, params=params, timeout=timeout_seconds)
            if response.status_code >= 400:
                return tool_error(
                    "Reverse-geocoding failed upstream.",
                    fix_hint="5xx responses are transient — retry once. 4xx means the coordinate was rejected; verify lat/lng ranges and retry.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            data = response.json()
            if data["status"] != "OK":
                return tool_error(
                    f"Reverse-geocoding returned status '{data.get('status', 'Unknown')}'.",
                    fix_hint="The coordinate may fall outside populated areas. If you only need an approximate label, proceed without a formatted address.",
                    extra={"upstream_status": data.get("status"), "error_message": data.get("error_message")},
                )
            await insert_api_cache(cache_key, data)

        results = data.get("results") or []
        if not results or not results[0].get("formatted_address"):
            return tool_error(
                "Reverse-geocoding returned no address.",
                fix_hint="The coordinate may fall in ocean or an unpopulated area. Proceed without a formatted address.",
            )
        return {"address": results[0].get("formatted_address", "")}

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Reverse-geocoding raised an unexpected error.",
            fix_hint="Retry once. If it fails again, proceed without a formatted address.",
            extra={"exception": str(e)},
        )

async def get_optimal_route(origin: Annotated[Location, Field(description="The origin location.")], destinations: Annotated[List[Location], Field(description="The list of destinations.")],
                            timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_optimal_route'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    if not origin:
        return tool_error(
            "An origin is required to calculate a route.",
            fix_hint="Retry with `origin` populated.",
        )

    if not destinations or len(destinations) == 0:
        return tool_error(
            "At least one destination is required to calculate a route.",
            fix_hint="Retry with a non-empty `destinations` list.",
        )

    if origin.lat is None or origin.lng is None:
        originCoordinates = await get_coordinates(origin.addressOrName, timeout_seconds)
        if "error" in originCoordinates:
            return tool_error(
                f"Could not geocode origin '{origin.addressOrName}'.",
                fix_hint="Populate `origin.lat` and `origin.lng` directly, or simplify the address string and retry.",
                extra={"upstream_error": originCoordinates},
            )
        origin.lat = originCoordinates.get("lat")
        origin.lng = originCoordinates.get("lng")

    for idx, destination in enumerate(destinations):
        if destination.lat is None or destination.lng is None:
            destinationCoordinates = await get_coordinates(destination.addressOrName, timeout_seconds)
            if "error" in destinationCoordinates:
                return tool_error(
                    f"Could not geocode destinations[{idx}] '{destination.addressOrName}'.",
                    fix_hint="Populate this destination's `lat` and `lng` directly, or simplify its address string and retry.",
                    extra={"upstream_error": destinationCoordinates},
                )
            destination.lat = destinationCoordinates.get("lat")
            destination.lng = destinationCoordinates.get("lng")

    cache_key = await generate_cache_key("get_optimal_route", {"origin": origin.model_dump(), "destinations": [destination.model_dump() for destination in destinations]})
    cache_value = await retrieve_api_cache(cache_key, expires_in=31)
    if cache_value:
        return cache_value

    best_sequence = []
    min_total_distance = float('inf')

    # Generate every possible order of visiting the destinations
    # Since we always start and end at the same origin, we only permute the middle
    for permutation in itertools.permutations(destinations):
        current_distance = 0
        current_path = [origin] + list(permutation) + [origin]
        for i in range(len(current_path) - 1):
            p1 = (current_path[i].lat, current_path[i].lng)
            p2 = (current_path[i+1].lat, current_path[i+1].lng)
            current_distance += await haversineDistance(p1, p2)

        if current_distance < min_total_distance:
            min_total_distance = current_distance
            best_sequence = current_path

    route_names = [loc.addressOrName for loc in best_sequence]

    returnData = {
        "optimalSequence": [loc.model_dump() for loc in best_sequence],
        "totalDistanceMiles": round(min_total_distance * 0.621371, 2)
    }
    await insert_api_cache(cache_key, returnData)
    return returnData


PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_coordinates.__doc__ = (PROMPTS_DIR / "get_coordinates.md").read_text()
get_address.__doc__ = (PROMPTS_DIR / "get_address.md").read_text()
get_optimal_route.__doc__ = (PROMPTS_DIR / "get_optimal_route.md").read_text()
