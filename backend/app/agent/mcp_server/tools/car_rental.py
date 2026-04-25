from typing import Dict, Annotated, List, Optional, Literal
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools._errors import tool_error
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import SKU

def _car_rental_quota_error(exc: "RateLimitExceeded") -> Dict:
    return tool_error(
        f"Monthly quota exhausted for SKU '{exc.sku}'.",
        fix_hint=f"Do not retry. Skip this and proceed with what you have. Retry after {exc.retry_after_seconds}s.",
        status_code=429,
        extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
    )

rapid_api_key = settings.RAPID_API_KEY

class Coordinates(BaseModel):
    latitude: Annotated[float, Field(ge=-90.0, le=90.0, description="The latitude of the coordinates.")]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0, description="The longitude of the coordinates.")]

class DateTime(BaseModel):
    date: Annotated[str, Field(description="The date in format YYYY-MM-DD.")]
    time: Annotated[str, Field(description="The time in format HH:MM.")]

carTypes = Literal["small", "medium", "large", "estate", "premium", "carriers", "suvs"]

async def format_rental_cars(data: Dict, searchKey: str) -> Dict:
    supplierInfo = {
        "name": data.get("supplier_info", {}).get("name", ""),
        "logoUrl": data.get("supplier_info", {}).get("logo_url", ""),
        "pickupInstructions": data.get("supplier_info", {}).get("pickup_instructions", ""),
        "dropoffInstructions": data.get("supplier_info", {}).get("dropoff_instructions", ""),
    }
    vehicleInfo = {
        "vehicleId": data.get("vehicle_info", {}).get("v_id", ""),
        "vehicleName": data.get("vehicle_info", {}).get("v_name", ""),
        "vehicleTransmission": data.get("vehicle_info", {}).get("transmission", ""),
        "vehicleSeats": data.get("vehicle_info", {}).get("seats", ""),
        "vehicleDoors": data.get("vehicle_info", {}).get("doors", ""),
        "mileage": data.get("vehicle_info", {}).get("mileage", ""),
        "fuelType": data.get("vehicle_info", {}).get("fuel_type", ""),
        "freeCancellation": True if data.get("vehicle_info", {}).get("free_cancellation", 0) == 1 else False,
        "airbags": True if data.get("vehicle_info", {}).get("airbags", 0) == 1 else False,
        "group": data.get("vehicle_info", {}).get("group", ""),
    }
    pickupInfo = {
        "name": data.get("route_info", {}).get("pickup", {}).get("name", ""),
        "address": data.get("route_info", {}).get("pickup", {}).get("address", ""),
        "coordinates": {
            "latitude": data.get("route_info", {}).get("pickup", {}).get("latitude", ""),
            "longitude": data.get("route_info", {}).get("pickup", {}).get("longitude", ""),
        },
    }
    dropOffInfo = {
        "name": data.get("route_info", {}).get("dropoff", {}).get("name", ""),
        "address": data.get("route_info", {}).get("dropoff", {}).get("address", ""),
        "coordinates": {
            "latitude": data.get("route_info", {}).get("dropoff", {}).get("latitude", ""),
            "longitude": data.get("route_info", {}).get("dropoff", {}).get("longitude", ""),
        },
    }
    routeInfo = {
        "pickupInfo": pickupInfo,
        "dropOffInfo": dropOffInfo,
    }
    ratingInfo = data.get("rating_info", {})
    pricingInfo = {
        "priceInUSD": data.get("pricing_info", {}).get("drive_away_price", ""),
        "description": data.get("pay_when_text", ""),
    }
    return {
        "supplierInfo": supplierInfo,
        "vehicleInfo": vehicleInfo,
        "routeInfo": routeInfo,
        "ratingInfo": ratingInfo,
        "pricingInfo": pricingInfo,
        "bookingUrl": f"https://cars.booking.com/package/deal/{searchKey}/{data.get('vehicle_info', {}).get('v_id', '')}",
    }

# RapidAPI Booking.com API
async def search_rental_cars(pickupCoordinates: Annotated[Coordinates, Field(description="The coordinates of the pickup location.")],
                       pickupDateTime: Annotated[DateTime, Field(description="The date and time of the pickup according to the wall clock time of the pickup location.")],
                       dropOffDateTime: Annotated[DateTime, Field(description="The date and time of the dropoff according to the wall clock time of the dropoff location.")],
                       dropOffCoordinates: Annotated[Optional[Coordinates], Field(description="(Optional) The coordinates of the dropoff location.", default=None)],
                       sortBy: Annotated[Optional[Literal["recommended", "price_low_to_high"]], Field(description="(Optional) The field to sort the results by. Either recommended or lowest price first. Default is recommended.", default="recommended")],
                       carTypes: Annotated[Optional[List[carTypes]], Field(description="(Optional) The types of cars to search for.", default=None)],
                       driverAge: Annotated[Optional[int], Field(description="(Optional) The age of the driver.", default=None)],
                       units: Annotated[Optional[Literal["METRIC", "IMPERIAL"]], Field(description="(Optional) The units to use for the results.", default="IMPERIAL")],
                       resultsPerPage: Annotated[Optional[int], Field(ge=5, le=50, description="(Optional) The number of results to return per page (min 5, max 50).", default=10)],
                       page: Annotated[Optional[int], Field(ge=1, description="(Optional) The page number to return (1-based).", default=1)],
                       timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['search_rental_cars'])]) -> Dict:

    if not rapid_api_key:
        return tool_error(
            "Rental-car search provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed with the trip plan without this rental-car search.",
        )
    missing = [
        name
        for name, val in (
            ("pickupCoordinates", pickupCoordinates),
            ("pickupDateTime", pickupDateTime),
            ("dropOffDateTime", dropOffDateTime),
        )
        if not val
    ]
    if missing:
        return tool_error(
            f"Required parameters are missing: {missing}.",
            fix_hint="Retry with `pickupCoordinates`, `pickupDateTime`, and `dropOffDateTime` all populated.",
        )
    url = "https://booking-com18.p.rapidapi.com/car/search-coordinates"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "booking-com18.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    params = {
        "pickUpCoord" : f"{pickupCoordinates.latitude},{pickupCoordinates.longitude}",
        "pickUpDate" : pickupDateTime.date,
        "pickUpTime" : pickupDateTime.time,
        "dropOffDate" : dropOffDateTime.date,
        "dropOffTime" : dropOffDateTime.time,
        "sortBy" : sortBy,
        "units" : units,
        "currencyCode" : "USD",
    }
    if dropOffCoordinates:
        params["dropOffCoord"] = f"{dropOffCoordinates.latitude},{dropOffCoordinates.longitude}"
    if driverAge:
        params["driverAge"] = driverAge
    if carTypes:
        carType = ",".join("carCategory::" + car for car in carTypes)
        params["carType"] = carType
    # Rate-limit gate.
    try:
        await get_rate_limiter().consume(SKU["booking_com"], cache_hit=False)
    except RateLimitExceeded as exc:
        return _car_rental_quota_error(exc)
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Rental-car search failed upstream.",
                fix_hint="Verify pickup < dropoff, dates in the future, valid coordinates, and retry. 5xx responses are transient — try once more; 4xx usually means invalid args.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        data = data.get("data", {})
        searchKey = data.get("search_key", "")
        rentalCars = data.get("search_results", [])
        totalResults = data.get("count", len(rentalCars))
        totalPages = max(1, (totalResults + resultsPerPage - 1) // resultsPerPage) if resultsPerPage else 1
        startIndex = (page - 1) * resultsPerPage
        endIndex = startIndex + resultsPerPage
        if startIndex >= len(rentalCars):
            return tool_error(
                f"`page` {page} is out of range.",
                fix_hint=f"This search has {totalResults} total result(s) and {totalPages} page(s) at resultsPerPage={resultsPerPage}. Retry with a `page` in [1, {totalPages}].",
                extra={"page_length": len(rentalCars), "total_results": totalResults, "total_pages": totalPages},
            )
        rentalCars = rentalCars[startIndex:endIndex]
        if not rentalCars:
            return tool_error(
                "No rental cars returned for this page.",
                fix_hint="Retry with page=1, or broaden the search (wider pickup/dropoff window, remove carTypes filter).",
            )
        result = {}
        result["totalResults"] = totalResults
        result["totalPages"] = totalPages
        result["page"] = page
        result["rentalCarOptions"] = [await format_rental_cars(rentalCar, searchKey) for rentalCar in rentalCars]
        result["hasMorePages"] = totalResults > endIndex
        result["nextPage"] = page + 1 if result["hasMorePages"] else None
        return result

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Rental-car search raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without rental-car data.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_rental_cars.__doc__ = (PROMPTS_DIR / "search_rental_cars.md").read_text()
