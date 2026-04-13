import requests
from typing import Dict, Annotated, List, Optional, Literal
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.agent.mcp_server.tools.timezone import convert_target_local_time_to_utc, get_timezone
from app.agent.mcp_server.tools.geocoding import get_coordinates
import time
from datetime import datetime
import math

rapid_api_key = settings.RAPID_API_KEY

class SearchCoordinates(BaseModel):
    latitude: Annotated[float, Field(ge=-90.0, le=90.0, description="The latitude of the coordinates.")]
    longitude: Annotated[float, Field(ge=-180.0, le=180.0, description="The longitude of the coordinates.")]
    radiusKm: Annotated[float, Field(ge=1.0, le=100.0, description="The radius in kilometers around the coordinates.", default=5.0)]

def get_bounding_box(searchCoordinates: Annotated[SearchCoordinates, Field(description="The coordinates of the search location.")]) -> Dict:
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

def format_hotel_data(data: Dict) -> Dict:
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
            "propertyReviewsCount": data.get("basicPropertyData", {}).get("reviews", {}).get("reviewsCount", None),
            "propertyReviewsSummary": data.get("basicPropertyData", {}).get("reviews", {}).get("totalScoreTextTag", {}).get("translation", None),
        },
        "propertyStarRating": data.get("basicPropertyData", {}).get("starRating", None)
    }
    checkInOutInfo = {
        "checkInTimeFromFormatted": data.get("checkinCheckoutPolicy", {}).get("checkinTimeFromFormatted", None),
        "checkOutTimeUntilFormatted": data.get("checkinCheckoutPolicy", {}).get("checkoutTimeUntilFormatted", None)
    }
    priceInfo = {
        "priceForStayInUSD": data.get("priceDisplayInfo", {}).get("displayPrice", {}).get("amountPerStay", {}).get("amountUnformatted", None),
        "priceForStayText": data.get("priceDisplayInfo", {}).get("displayPrice", {}).get("amountPerStay", {}).get("amountRounded", None)
    }
    rooms = []
    for block in data.get("blocks", []):
        rooms.append({
            "roomId": block.get("blockId", {}).get("roomId", None),
            "occupancy": block.get("blockId", {}).get("occupancy", None),
            "mealPlanId": block.get("blockId", {}).get("mealPlanId", None),
            "freeCancellationUntilUTC": block.get("freeCancellationUntil", None)
        })
    return {
        "propertyInfo": propertyInfo,
        "checkInOutInfo": checkInOutInfo,
        "priceInfo": priceInfo,
        "rooms": rooms,
        "isSoldOut": data.get("soldOutInfo", {}).get("isSoldOut", False)
    }

# RapidAPI Booking.com API
def search_hotels(searchCoordinates: Annotated[SearchCoordinates, Field(description="The coordinates of the search location.")],
                  checkinDate: Annotated[str, Field(description="The checkin date in format YYYY-MM-DD.")],
                  checkoutDate: Annotated[str, Field(description="The checkout date in format YYYY-MM-DD.")],
                  rooms: Annotated[Optional[int], Field(ge=1, le=30, description="The number of rooms to search for.", default=1)],
                  adults: Annotated[Optional[int], Field(ge=1, le=30, description="The number of adults to search for.", default=1)],
                  children: Annotated[Optional[List[int]], Field(description="List of children ages to search for. Ranging from 0 to 17.", default=None)],
                  minPrice: Annotated[Optional[int], Field(ge=0, description="The minimum price to search for in USD.", default=None)],
                  maxPrice: Annotated[Optional[int], Field(ge=0, description="The maximum price to search for in USD.", default=None)],
                  resultsPerPage: Annotated[Optional[int], Field(ge=5, le=50, description="The number of results to return per page.", default=10)],
                  page: Annotated[Optional[int], Field(ge=1, description="The page number to return.", default=1)],
                  units: Annotated[Optional[Literal["METRIC", "IMPERIAL"]], Field(description="The units to use for the results.", default="IMPERIAL")]) -> Dict:
    if not rapid_api_key:
        return {"error": "RapidAPI key is required"}
    if not searchCoordinates or not checkinDate or not checkoutDate:
        return {"error": "Required parameters are missing"}
    
    url = "https://booking-com18.p.rapidapi.com/stays/search-by-geo"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "booking-com18.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    boundingBox = get_bounding_box(searchCoordinates)
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
            return {"error": "Minimum price must be less than maximum price"}
        params["minPrice"] = minPrice
        params["maxPrice"] = maxPrice
    elif minPrice:
        params["minPrice"] = minPrice
    elif maxPrice:
        params["maxPrice"] = maxPrice
    try:
        response = requests.get(url, headers=headers, params=params, timeout=45)
        if not response.ok:
            return {"error": f"Failed to search hotels: {response.status_code} {response.text}"}
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
        returnData["hotels"] = [format_hotel_data(hotel) for hotel in results]
        return returnData
    except Exception as e:
        return {"error": f"Failed to search hotels: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_hotels.__doc__ = (PROMPTS_DIR / "search_hotels.md").read_text()