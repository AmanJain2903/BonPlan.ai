import requests
from typing import Dict, Optional, Annotated, Literal, List
from pydantic import Field
from app.core.config import settings
from app.agent.mcp_server.tools.constants import GoogleFieldMasks, GooglePlaceType
import pathlib
from app.agent.mcp_server.caching import generate_cache_key, retrieve_api_cache, insert_api_cache

api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED

# Places API
def search_places(query: Annotated[str, Field(description="The general or specific text query string to search for real-world places.")], 
                  max_results: Annotated[int, Field(ge=1, le=10, description="The maximum number of results to return (min 1, max 10).", default=5)],
                  next_page_token: Annotated[Optional[str], Field(description="The next page token to continue the search from. Optional. If provided, the search will continue from the next page.", default=None)],
                  place_index: Annotated[Optional[int], Field(description="The index of the place to return from the search results.", default=0)]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    cache_key = generate_cache_key("search_places", {"query": query.lower().strip(), "max_results": max_results, "next_page_token": next_page_token})
    cache_value = retrieve_api_cache(cache_key)
    
    url = "https://places.googleapis.com/v1/places:searchText"
    body = {
        "textQuery": query,
        "maxResultCount": max_results,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["places"]["textSearch"],
    }
    if next_page_token:
        body["pageToken"] = next_page_token

    try:
        if cache_value:
            data = cache_value.get("places", [])
        else:
            response = requests.post(url, json=body, headers=headers, timeout=5)
            if not response.ok:
                return {"error": f"Places API error: {response.status_code} {response.text}"}
            data = response.json()
            insert_api_cache(cache_key, {"places": data})

        if place_index >= len(data.get("places", [])):
            return {"error": "Place index out of range"}
        
        place = data.get("places", [])[place_index]
        placeOutput = {
                "id": place.get("id"),
                "name": place.get("displayName", {}).get("text", ""),
                "type": {
                    "primaryType": place.get("primaryType", ""),
                    "primaryTypeName": place.get("primaryTypeDisplayName", {}).get("text", ""),
                    "types": place.get("types", []),
                },
                "placeSummaries": {
                    "editorialSummary": place.get("editorialSummary", {}).get("text", ""),
                    "generativeSummary": place.get("generativeSummary", {}).get("overview", {}).get("text", ""),
                    "neighborhoodSummary": place.get("neighborhoodSummary", {}).get("overview", {}).get("content", {}).get("text", ""),
                },
                "location": {
                    "address": place.get("formattedAddress", ""),
                    "latitude": place.get("location", {}).get("latitude", None),
                    "longitude": place.get("location", {}).get("longitude", None),
                },
                "phoneNumber": place.get("internationalPhoneNumber", ""),
                "reviews": {
                    "rating": place.get("rating", None),
                    "userRatingCount": place.get("userRatingCount", None),
                    "reviewSummary": place.get("reviewSummary", {}).get("text", {}).get("text", ""),
                },
                "urls" : {
                    "googleMaps": place.get("googleMapsUri", ""),
                    "website": place.get("websiteUri", ""),
                },
                "icon": {
                    "backgroundColor": place.get("iconBackgroundColor", None),
                    "maskBaseUri": place.get("iconMaskBaseUri", ""),
                },
                "accessibilityOptions": place.get("accessibilityOptions", {}),
                "photos": place.get("photos", []),
                "businessStatus": place.get("businessStatus", ""),
                "openingHours": {
                    "current": {
                        "openNow": place.get("currentOpeningHours", {}).get("openNow", None),
                        "weekdayDescriptions": place.get("currentOpeningHours", {}).get("weekdayDescriptions", None),
                        "nextOpenTime": place.get("currentOpeningHours", {}).get("nextOpenTime", None),
                        "nextCloseTime": place.get("currentOpeningHours", {}).get("nextCloseTime", None),
                    },
                    "regular": {
                        "openNow": place.get("regularOpeningHours", {}).get("openNow", None),
                        "weekdayDescriptions": place.get("regularOpeningHours", {}).get("weekdayDescriptions", None),
                        "nextOpenTime": place.get("regularOpeningHours", {}).get("nextOpenTime", None),
                        "nextCloseTime": place.get("regularOpeningHours", {}).get("nextCloseTime", None),
                    },
                    "currentSecondary": place.get("currentSecondaryOpeningHours", {}),
                    "regularSecondary": place.get("regularSecondaryOpeningHours", {}),
                },
                "priceRange": place.get("priceRange", None),
                "priceLevel": place.get("priceLevel", None),
                "parkingOptions": place.get("parkingOptions", None),
                "paymentOptions": place.get("paymentOptions", None),
                "fuelOptions": place.get("fuelOptions", None),
                "evChargeOptions": place.get("evChargeOptions", None),
                "otherOptions": {
                    "allowsDogs": place.get("allowsDogs", None),
                    "curbsidePickup": place.get("curbsidePickup", None),
                    "delivery": place.get("delivery", None),
                    "dineIn": place.get("dineIn", None),
                    "takeout": place.get("takeout", None),
                    "goodForChildren": place.get("goodForChildren", None),
                    "goodForGroups": place.get("goodForGroups", None),
                    "goodForWatchingSports": place.get("goodForWatchingSports", None),
                    "liveMusic": place.get("liveMusic", None),
                    "menuForChildren": place.get("menuForChildren", None),
                    "outdoorSeating": place.get("outdoorSeating", None),
                    "reservable": place.get("reservable", None),
                    "restroom": place.get("restroom", None),
                    "servesBeer": place.get("servesBeer", None),
                    "servesBreakfast": place.get("servesBreakfast", None),
                    "servesBrunch": place.get("servesBrunch", None),
                    "servesCocktails": place.get("servesCocktails", None),
                    "servesCoffee": place.get("servesCoffee", None),
                    "servesDessert": place.get("servesDessert", None),
                    "servesDinner": place.get("servesDinner", None),
                    "servesLunch": place.get("servesLunch", None),
                    "servesVegetarianFood": place.get("servesVegetarianFood", None),
                    "servesWine": place.get("servesWine", None),
                    "takeout": place.get("takeout", None),
                },
            }
        
        return {
            "place": placeOutput,
            "nextPageToken": data.get("nextPageToken", None),
            "hasNext": len(data.get("places", [])) > place_index + 1,
            "nextIndex": place_index + 1 if len(data.get("places", [])) > place_index + 1 else None,
        }

    except Exception as e:
        return {"error": f"Places API error: {str(e)}"}

def search_places_nearby(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the central location as a float.")], 
                        lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the central location as a float.")], 
                        included_types: Annotated[List[GooglePlaceType], Field(description="The list of valid GooglePlaceType literal strings to search for.")],
                        radius: Annotated[float, Field(ge=10.0, le=50000.0, description="The search radius in meters around the specified location.", default=500)], 
                        max_results: Annotated[int, Field(ge=10, le=20, description="The maximum number of results to return (min 10, max 20).", default=20)],
                        rank_preference: Annotated[Literal["POPULARITY", "DISTANCE"], Field(description="The preference determining how the returned places are ranked.", default="POPULARITY")],
                        excluded_types: Annotated[Optional[List[GooglePlaceType]], Field(description="The types of places to explicitly exclude from the search results.", default=None)],
                        place_index: Annotated[int, Field(description="The index of the place to return from the search results.", default=0)]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    cache_key = generate_cache_key("search_places_nearby", {"lat": lat, "lng": lng, "included_types": included_types, "radius": radius, "max_results": max_results, "rank_preference": rank_preference, "excluded_types": excluded_types})
    cache_value = retrieve_api_cache(cache_key)
    
    url = "https://places.googleapis.com/v1/places:searchNearby"
    body = {
        "includedTypes": included_types,
        "excludedTypes": excluded_types,
        "maxResultCount": max_results,
        "rankPreference": rank_preference,
        "locationRestriction": {
            "circle": {
              "center": {
                "latitude": lat,
                "longitude": lng
                },
              "radius": radius
            }
  }
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["places"]["nearbySearch"],
    }
    try:
        if cache_value:
            data = cache_value.get("places", [])
        else:
            response = requests.post(url, json=body, headers=headers, timeout=5)
            if not response.ok:
                return {"error": f"Places API error: {response.status_code} {response.text}"}
            data = response.json()
            insert_api_cache(cache_key, {"places": data})
        
        if len(data.get("places", [])) == 0:
            return {"error": "No places found. Try adjusting the search parameters."}

        if place_index >= len(data.get("places", [])):
            return {"error": "Place index out of range"}
        
        place = data.get("places", [])[place_index]
        return {
            "place": {
                "id": place.get("id"),
                "name": place.get("displayName", {}).get("text", ""),
                "type": {
                    "primaryType": place.get("primaryType", ""),
                    "primaryTypeName": place.get("primaryTypeDisplayName", {}).get("text", ""),
                    "types": place.get("types", []),
                },
                "placeSummaries": {
                    "editorialSummary": place.get("editorialSummary", {}).get("text", ""),
                    "generativeSummary": place.get("generativeSummary", {}).get("overview", {}).get("text", ""),
                    "neighborhoodSummary": place.get("neighborhoodSummary", {}).get("overview", {}).get("content", {}).get("text", ""),
                },
                "location": {
                    "address": place.get("formattedAddress", ""),
                    "latitude": place.get("location", {}).get("latitude", None),
                    "longitude": place.get("location", {}).get("longitude", None),
                },
                "phoneNumber": place.get("internationalPhoneNumber", ""),
                "reviews": {
                    "rating": place.get("rating", None),
                    "userRatingCount": place.get("userRatingCount", None),
                    "reviewSummary": place.get("reviewSummary", {}).get("text", {}).get("text", ""),
                },
                "urls" : {
                    "googleMaps": place.get("googleMapsUri", ""),
                    "website": place.get("websiteUri", ""),
                },
                "icon": {
                    "backgroundColor": place.get("iconBackgroundColor", None),
                    "maskBaseUri": place.get("iconMaskBaseUri", ""),
                },
                "accessibilityOptions": place.get("accessibilityOptions", {}),
                "photos": place.get("photos", []),
                "businessStatus": place.get("businessStatus", ""),
                "openingHours": {
                    "current": {
                        "openNow": place.get("currentOpeningHours", {}).get("openNow", None),
                        "weekdayDescriptions": place.get("currentOpeningHours", {}).get("weekdayDescriptions", None),
                        "nextOpenTime": place.get("currentOpeningHours", {}).get("nextOpenTime", None),
                        "nextCloseTime": place.get("currentOpeningHours", {}).get("nextCloseTime", None),
                    },
                    "regular": {
                        "openNow": place.get("regularOpeningHours", {}).get("openNow", None),
                        "weekdayDescriptions": place.get("regularOpeningHours", {}).get("weekdayDescriptions", None),
                        "nextOpenTime": place.get("regularOpeningHours", {}).get("nextOpenTime", None),
                        "nextCloseTime": place.get("regularOpeningHours", {}).get("nextCloseTime", None),
                    },
                    "currentSecondary": place.get("currentSecondaryOpeningHours", {}),
                    "regularSecondary": place.get("regularSecondaryOpeningHours", {}),
                },
                "priceRange": place.get("priceRange", None),
                "priceLevel": place.get("priceLevel", None),
                "parkingOptions": place.get("parkingOptions", None),
                "paymentOptions": place.get("paymentOptions", None),
                "fuelOptions": place.get("fuelOptions", None),
                "evChargeOptions": place.get("evChargeOptions", None),
                "otherOptions": {
                    "allowsDogs": place.get("allowsDogs", None),
                    "curbsidePickup": place.get("curbsidePickup", None),
                    "delivery": place.get("delivery", None),
                    "dineIn": place.get("dineIn", None),
                    "takeout": place.get("takeout", None),
                    "goodForChildren": place.get("goodForChildren", None),
                    "goodForGroups": place.get("goodForGroups", None),
                    "goodForWatchingSports": place.get("goodForWatchingSports", None),
                    "liveMusic": place.get("liveMusic", None),
                    "menuForChildren": place.get("menuForChildren", None),
                    "outdoorSeating": place.get("outdoorSeating", None),
                    "reservable": place.get("reservable", None),
                    "restroom": place.get("restroom", None),
                    "servesBeer": place.get("servesBeer", None),
                    "servesBreakfast": place.get("servesBreakfast", None),
                    "servesBrunch": place.get("servesBrunch", None),
                    "servesCocktails": place.get("servesCocktails", None),
                    "servesCoffee": place.get("servesCoffee", None),
                    "servesDessert": place.get("servesDessert", None),
                    "servesDinner": place.get("servesDinner", None),
                    "servesLunch": place.get("servesLunch", None),
                    "servesVegetarianFood": place.get("servesVegetarianFood", None),
                    "servesWine": place.get("servesWine", None),
                    "takeout": place.get("takeout", None),
                    },
            },
            "hasNext": len(data.get("places", [])) > place_index + 1,
            "nextIndex": place_index + 1 if len(data.get("places", [])) > place_index + 1 else None,
            }
     

    except Exception as e:
        return {"error": f"Places API error: {str(e)}"}

def get_place_info(place_id: Annotated[str, "The Google Place ID of the place to get information about."]) -> dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    cache_key = generate_cache_key("get_place_info", {"place_id": place_id})
    cache_value = retrieve_api_cache(cache_key)
    
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": GoogleFieldMasks["places"]["placeInfo"],
    }
    try:
        if cache_value:
            data = cache_value.get("place", {})
        else:
            response = requests.get(url, headers=headers, timeout=5)
            if not response.ok:
                return {"error": f"Places API error: {response.status_code} {response.text}"}
            data = response.json()
            insert_api_cache(cache_key, {"place": data})
        
        if not data:
            return {"error": "No place info found for this request"}
        
        return {
            "place": {
                "id": data.get("id"),
                "name": data.get("displayName", {}).get("text", ""),
                "type": {
                    "primaryType": data.get("primaryType", ""),
                    "primaryTypeName": data.get("primaryTypeDisplayName", {}).get("text", ""),
                    "types": data.get("types", []),
                },
                "location": {
                    "address": data.get("formattedAddress", ""),
                    "latitude": data.get("location", {}).get("latitude", None),
                    "longitude": data.get("location", {}).get("longitude", None),
                },
                "phoneNumber": data.get("internationalPhoneNumber", ""),
                "reviews": {
                    "rating": data.get("rating", None),
                    "userRatingCount": data.get("userRatingCount", None)
                },
                "urls" : {
                    "googleMaps": data.get("googleMapsUri", ""),
                    "website": data.get("websiteUri", ""),
                },
                "icon": {
                    "backgroundColor": data.get("iconBackgroundColor", None),
                    "maskBaseUri": data.get("iconMaskBaseUri", None),
                },
                "accessibilityOptions": data.get("accessibilityOptions", {}),
                "photos": data.get("photos", []),
                "businessStatus": data.get("businessStatus", ""),
                "openingHours": {
                    "current": {
                        "openNow": data.get("currentOpeningHours", {}).get("openNow", None),
                        "weekdayDescriptions": data.get("currentOpeningHours", {}).get("weekdayDescriptions", None),
                        "nextOpenTime": data.get("currentOpeningHours", {}).get("nextOpenTime", None),
                        "nextCloseTime": data.get("currentOpeningHours", {}).get("nextCloseTime", None),
                    },
                    "regular": {
                        "openNow": data.get("regularOpeningHours", {}).get("openNow", None),
                        "weekdayDescriptions": data.get("regularOpeningHours", {}).get("weekdayDescriptions", None),
                        "nextOpenTime": data.get("regularOpeningHours", {}).get("nextOpenTime", None),
                        "nextCloseTime": data.get("regularOpeningHours", {}).get("nextCloseTime", None),
                    },
                    "currentSecondary": data.get("currentSecondaryOpeningHours", {}),
                    "regularSecondary": data.get("regularSecondaryOpeningHours", {}),
                },
                "priceRange": data.get("priceRange", None),
                "priceLevel": data.get("priceLevel", None)
            }
        }
    except Exception as e:
        return {"error": f"Places API error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_places.__doc__ = (PROMPTS_DIR / "search_places.md").read_text()
search_places_nearby.__doc__ = (PROMPTS_DIR / "search_places_nearby.md").read_text()
get_place_info.__doc__ = (PROMPTS_DIR / "get_place_info.md").read_text()