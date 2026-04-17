from typing import Dict, Annotated, List, Optional, Literal
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
from app.agent.mcp_server.tools.timezone import convert_target_local_time_to_utc, get_timezone
from app.agent.mcp_server.tools.geocoding import get_coordinates
from app.agent.mcp_server.tools._errors import tool_error
import time
from datetime import datetime

rapid_api_key = settings.RAPID_API_KEY

class Coordinates(BaseModel):
    latitude: Annotated[float, Field(ge=-90.0, le=90.0, description="The latitude of the coordinates.")]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0, description="The longitude of the coordinates.")]

class DateTime(BaseModel):
    date: Annotated[str, Field(description="The date in format YYYY-MM-DD.")]
    time: Annotated[str, Field(description="The time in format HH:MM.")]

carTypes = Literal["small", "medium", "large", "estate", "premium", "carriers", "suvs"]

def format_rental_cars(data: Dict) -> Dict:
    supplierInfo = {
        "name": data.get("supplier_info", {}).get("name", ""),
        "logoUrl": data.get("supplier_info", {}).get("logo_url", ""),
        "pickupInstructions": data.get("supplier_info", {}).get("pickup_instructions", ""),
        "dropoffInstructions": data.get("supplier_info", {}).get("dropoff_instructions", ""),
    }
    vehicleInfo = {
        "vehicleId": data.get("vehicle_info", {}).get("v_id", ""),
        "vehicleName": data.get("vehicle_info", {}).get("v_name", ""),
        "vehicleImageUrl": data.get("vehicle_info", {}).get("image_url", ""),
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
        "locationId": data.get("route_info", {}).get("pickup", {}).get("location_id", ""),
        "name": data.get("route_info", {}).get("pickup", {}).get("name", ""),
        "address": data.get("route_info", {}).get("pickup", {}).get("address", ""),
        "coordinates": {
            "latitude": data.get("route_info", {}).get("pickup", {}).get("latitude", ""),
            "longitude": data.get("route_info", {}).get("pickup", {}).get("longitude", ""),
        },
    }
    dropOffInfo = {
        "locationId": data.get("route_info", {}).get("dropoff", {}).get("location_id", ""),
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
        "price": data.get("pricing_info", {}).get("drive_away_price", ""),
        "currency": data.get("pricing_info", {}).get("currency", ""),
        "description": data.get("pay_when_text", ""),
    }
    return {
        "supplierInfo": supplierInfo,
        "vehicleInfo": vehicleInfo,
        "routeInfo": routeInfo,
        "ratingInfo": ratingInfo,
        "pricingInfo": pricingInfo,
        "bookingUrl": data.get("forward_url", ""),
    }

# RapidAPI Booking.com API
async def search_rental_cars(pickupCoordinates: Annotated[Coordinates, Field(description="The coordinates of the pickup location.")],
                       pickupDateTime: Annotated[DateTime, Field(description="The date and time of the pickup according to the wall clock time of the pickup location.")],
                       dropOffDateTime: Annotated[DateTime, Field(description="The date and time of the dropoff according to the wall clock time of the dropoff location.")],
                       dropOffCoordinates: Annotated[Optional[Coordinates], Field(description="The coordinates of the dropoff location.", default=None)],
                       sortBy: Annotated[Optional[Literal["recommended", "price_low_to_high"]], Field(description="The field to sort the results by. Either recommended or lowest price first. Default is recommended.", default="recommended")],
                       carTypes: Annotated[Optional[List[carTypes]], Field(description="The types of cars to search for.", default=None)],
                       driverAge: Annotated[Optional[int], Field(description="The age of the driver.", default=None)],
                       units: Annotated[Optional[Literal["METRIC", "IMPERIAL"]], Field(description="The units to use for the results.", default="IMPERIAL")],
                       resultsPerPage: Annotated[Optional[int], Field(ge=5, le=50, description="The number of results to return per page (min 5, max 50).", default=10)],
                       page: Annotated[Optional[int], Field(ge=1, description="The page number to return (1-based).", default=1)]) -> Dict:

    if not rapid_api_key:
        return tool_error(
            "Rental-car search provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed with the trip plan without this rental-car search.",
        )
    if not pickupCoordinates or not pickupDateTime or not dropOffDateTime:
        return tool_error(
            "Required parameters are missing.",
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
    cache_key = generate_cache_key("search_rental_cars", params)
    cache_value = await retrieve_api_cache(cache_key, expires_in=1)
    try:
        if cache_value:
            data = cache_value
        else:
            client = get_http_client()
            response = await client.get(url, headers=headers, params=params, timeout=45)
            if response.status_code >= 400:
                return tool_error(
                    "Rental-car search failed upstream.",
                    fix_hint="Verify pickup < dropoff, dates in the future, valid coordinates, and retry. 5xx responses are transient — try once more; 4xx usually means invalid args.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            data = response.json()
            await insert_api_cache(cache_key, data)
        data = data.get("data", {})
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
        result["searchContext"] = data.get("search_context", {})
        result["rentalCarOptions"] = [format_rental_cars(rentalCar) for rentalCar in rentalCars]
        result["hasMorePages"] = totalResults > endIndex
        result["nextPage"] = page + 1 if result["hasMorePages"] else None
        return result

    except Exception as e:
        return tool_error(
            "Rental-car search raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without rental-car data.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_rental_cars.__doc__ = (PROMPTS_DIR / "search_rental_cars.md").read_text()