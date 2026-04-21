from typing import Dict, Annotated, List, Optional, Literal
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools._errors import tool_error
import math
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.agent.api.caching import generate_cache_key, retrieve_api_cache, insert_api_cache

rapid_api_key = settings.RAPID_API_KEY

class SearchCoordinates(BaseModel):
    latitude: Annotated[float, Field(ge=-90.0, le=90.0, description="The latitude of the coordinates.")]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0, description="The longitude of the coordinates.")]
    radiusKm: Annotated[float, Field(ge=1.0, le=100.0, description="The radius in kilometers around the coordinates.", default=5.0)]

async def get_bounding_box(searchCoordinates: Annotated[SearchCoordinates, Field(description="The coordinates of the search location.")]) -> Dict:
    # Earth's radius in kilometers
    R = 6371.0
    lat = searchCoordinates.latitude
    lng = searchCoordinates.longitude
    radius = searchCoordinates.radiusKm
    lat_offset = math.degrees(radius / R)
    lng_offset = math.degrees(radius / (R * math.cos(math.radians(lat))))
    return {
        "neLat": lat + lat_offset,
        "neLng": lng + lng_offset,
        "swLat": lat - lat_offset,
        "swLng": lng - lng_offset,
    }

async def format_hotel_data(data: Dict) -> Dict:
    if not data:
        return {}
    propertyInfo = {
        "propertyId": data.get("basicPropertyData", {}).get("id", None),
        "propertyName": data.get("basicPropertyData", {}).get("name", None),
        "propertyLocation": {
            "propertyAddress": data.get("basicPropertyData", {}).get("location", {}).get("address", None),
            "propertyCity": data.get("basicPropertyData", {}).get("location", {}).get("city", None),
            "propertyLatitude": data.get("basicPropertyData", {}).get("location", {}).get("latitude", None),
            "propertyLongitude": data.get("basicPropertyData", {}).get("location", {}).get("longitude", None),
            "propertyDistanceFromSearchPointInKm": data.get("basicPropertyData", {}).get("location", {}).get("distanceToPointOfSearchKm", None)
        },
        "propertyReviews": {
            "propertyRating": data.get("basicPropertyData", {}).get("reviews", {}).get("totalScore", None),
            "propertyReviewsSummary": data.get("basicPropertyData", {}).get("reviews", {}).get("totalScoreTextTag", {}).get("translation", None),
        },
        "propertyStarRating": data.get("basicPropertyData", {}).get("starRating", None)
    }
    checkInOutInfo = {
        "checkInTimeFromFormatted": data.get("checkinCheckoutPolicy", {}).get("checkinTimeFromFormatted", None),
        "checkOutTimeUntilFormatted": data.get("checkinCheckoutPolicy", {}).get("checkoutTimeUntilFormatted", None)
    }
    priceInfo = {
        "priceForStayInUSD": data.get("priceDisplayInfo", {}).get("displayPrice", {}).get("amountPerStay", {}).get("amountUnformatted", None)
    }
    return {
        "propertyInfo": propertyInfo,
        "checkInOutInfo": checkInOutInfo,
        "priceInfo": priceInfo,
        "isSoldOut": data.get("soldOutInfo", {}).get("isSoldOut", False)
    }

# RapidAPI Booking.com API
async def search_hotels(searchCoordinates: Annotated[SearchCoordinates, Field(description="The coordinates of the search location.")],
                  checkinDate: Annotated[str, Field(description="The checkin date in format YYYY-MM-DD.")],
                  checkoutDate: Annotated[str, Field(description="The checkout date in format YYYY-MM-DD.")],
                  rooms: Annotated[Optional[int], Field(ge=1, le=30, description="(Optional) The number of rooms to search for.", default=1)],
                  adults: Annotated[Optional[int], Field(ge=1, le=30, description="(Optional) The number of adults to search for.", default=1)],
                  children: Annotated[Optional[List[int]], Field(description="(Optional) List of children ages to search for. Ranging from 0 to 17.", default=None)],
                  minPrice: Annotated[Optional[int], Field(ge=0, description="(Optional) The minimum price to search for in USD.", default=None)],
                  maxPrice: Annotated[Optional[int], Field(ge=0, description="(Optional) The maximum price to search for in USD.", default=None)],
                  resultsPerPage: Annotated[Optional[int], Field(ge=5, le=50, description="(Optional) The number of results to return per page. Minimum 5, maximum 50.", default=10)],
                  page: Annotated[Optional[int], Field(ge=1, description="(Optional) The page number to return. Minimum 1.", default=1)],
                  units: Annotated[Optional[Literal["METRIC", "IMPERIAL"]], Field(description="(Optional) The units to use for the results.", default="IMPERIAL")],
                  timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout.", default=TIMEOUTS['search_hotels'])]) -> Dict:
    if not rapid_api_key:
        return tool_error(
            "Hotel search provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed with the trip plan without this hotel search.",
        )
    if not searchCoordinates or not checkinDate or not checkoutDate:
        return tool_error(
            "Required parameters are missing.",
            fix_hint="Retry with `searchCoordinates` (lat, lng, radiusKm), `checkinDate` (YYYY-MM-DD), and `checkoutDate` (YYYY-MM-DD) all populated.",
        )
    
    url = "https://booking-com18.p.rapidapi.com/stays/search-by-geo"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "booking-com18.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    boundingBox = await get_bounding_box(searchCoordinates)
    params = {
        "neLat": boundingBox["neLat"],
        "neLng": boundingBox["neLng"],
        "swLat": boundingBox["swLat"],
        "swLng": boundingBox["swLng"],
        "rooms": rooms,
        "adults": adults,
        "checkinDate": checkinDate,
        "checkoutDate": checkoutDate,
        "resultsPerPage": resultsPerPage,
        "page": page,
        "units": units,
        "currencyCode": "USD",
    }
    if children:
        params["children"] = ",".join(str(child) for child in children)
    if minPrice and maxPrice:
        if minPrice > maxPrice:
            return tool_error(
                "`minPrice` must be less than `maxPrice`.",
                fix_hint="Retry with `minPrice` strictly less than `maxPrice`, or drop one of them to remove the price filter.",
            )
        params["minPrice"] = minPrice
        params["maxPrice"] = maxPrice
    elif minPrice:
        params["minPrice"] = minPrice
    elif maxPrice:
        params["maxPrice"] = maxPrice
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Hotel search failed upstream.",
                fix_hint="Verify that check-in < check-out, that both dates are in the future, that coordinates/radius are reasonable, and retry. If the status is 5xx the upstream provider is temporarily unavailable — try once more.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        data = data.get("data", {})
        metaData = data.get("searchMeta", {})
        results = data.get("results", [])
        returnData = {}
        returnData["nbRooms"] = metaData.get("nbRooms", None)
        returnData["nbAdults"] = metaData.get("nbAdults", None)
        returnData["nbChildren"] = metaData.get("nbChildren", None)
        returnData["lengthOfStayInDays"] = metaData.get("dates", {}).get("lengthOfStayInDays", None)
        returnData["checkinDate"] = metaData.get("dates", {}).get("checkin", None)
        returnData["checkoutDate"] = metaData.get("dates", {}).get("checkout", None)
        returnData["hotels"] = [await format_hotel_data(hotel) for hotel in results]
        return returnData
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Hotel search raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without this hotel search and note it in your reasoning.",
            extra={"exception": str(e)},
        )
    
async def get_hotel_booking_url(hotel_id: Annotated[str, Field(description="The ID of the hotel to get the booking URL for.")],
                                checkinDate: Annotated[str, Field(description="The checkin date in format YYYY-MM-DD.")],
                                checkoutDate: Annotated[str, Field(description="The checkout date in format YYYY-MM-DD.")],
                                rooms: Annotated[Optional[int], Field(ge=1, le=30, description="(Optional) The number of rooms to search for.", default=1)],
                                adults: Annotated[Optional[int], Field(ge=1, le=30, description="(Optional) The number of adults to search for.", default=1)],
                                children: Annotated[Optional[List[int]], Field(description="(Optional) List of children ages to search for. Ranging from 0 to 17.", default=None)],
                                units: Annotated[Optional[Literal["metric", "imperial"]], Field(description="(Optional) The units to use for the results.", default="imperial")],
                                timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_hotel_booking_url'])]) -> Dict:
    if not hotel_id or not checkinDate or not checkoutDate:
        return tool_error(
            "Required parameters are missing.",
            fix_hint="Retry with `hotel_id`, `checkinDate` (YYYY-MM-DD), and `checkoutDate` (YYYY-MM-DD) all populated.",
        )
    if not rapid_api_key:
        return tool_error(
            "Hotel booking provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without the hotel booking URL.",
        )
    url = "https://booking-com18.p.rapidapi.com/stays/detail"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "booking-com18.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    params = {
        "hotelId": hotel_id,
        "checkinDate": checkinDate,
        "checkoutDate": checkoutDate,
        "rooms": rooms,
        "adults": adults,
        "units": units
    }
    if children:
        params["children"] = ",".join(str(child) for child in children)
    cache_key = await generate_cache_key("get_hotel_booking_url", params)
    cache_value = await retrieve_api_cache(cache_key, expires_in=7)
    if cache_value:
        return {
            "booking_url": cache_value.get("booking_url", "")
        }
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Hotel booking URL lookup failed upstream.",
                fix_hint="The `hotel_id` may have expired or the upstream is temporarily unavailable. Retry once; if it still fails, do a fresh search_hotels call to obtain a new hotel ID. If still fails, proceed without the hotel booking URL.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        if not data:
            return tool_error(
                "No results returned from the upstream.",
                fix_hint="The booking url may not be available, proceed without the hotel booking URL.")
        booking_url = (data.get("data", {}) or {}).get("url", "")
        if booking_url:
            await insert_api_cache(cache_key, {"booking_url": booking_url})
        return {
            "booking_url": booking_url
        }
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Hotel booking URL lookup raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without the hotel booking URL.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_hotels.__doc__ = (PROMPTS_DIR / "search_hotels.md").read_text()
get_hotel_booking_url.__doc__ = (PROMPTS_DIR / "get_hotel_booking_url.md").read_text()