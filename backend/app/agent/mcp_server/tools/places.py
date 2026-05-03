from typing import Dict, Optional, Annotated, Literal, List, get_args
from pydantic import Field
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools.constants import GoogleFieldMasks, GooglePlaceType, _PLACE_TYPE_SAMPLE
from app.agent.mcp_server.tools._errors import tool_error
import pathlib
from app.agent.api.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import (
    SKU,
    resolve_search_places_nearby_sku,
    resolve_search_places_sku,
)
from app.logging import get_mcp_logger

logger = get_mcp_logger("tools.places")

api_key = settings.GOOGLE_MAPS_API_KEY

_SUMMARY_MAX_CHARS = 300  # cap editorial/generative summaries to control response size

_DINING_OPTIONS_FIELD_MASKS = ["places.dineIn","places.servesBeer","places.servesCocktails","places.servesWine","places.servesVegetarianFood","places.servesBreakfast","places.servesCoffee","places.servesBrunch","places.servesLunch","places.servesDinner","places.servesDessert"]
_AMENITIES_FIELD_MASKS = ["places.allowsDogs","places.goodForChildren","places.goodForGroups","places.liveMusic","places.outdoorSeating","places.evChargeOptions","places.parkingOptions","places.paymentOptions"]


def _format_place(place: dict, include_dining_options: bool = False, include_amenities: bool = False) -> dict:
    """Shared place formatter for search_places, search_places_nearby, and get_place_info."""
    placeData = {
        "id": place.get("id"),
        "name": place.get("displayName", {}).get("text", ""),
        "type": place.get("primaryTypeDisplayName", {}).get("text", ""),
        "location": {
            "address": place.get("formattedAddress", ""),
            "latitude": place.get("location", {}).get("latitude"),
            "longitude": place.get("location", {}).get("longitude"),
        },
        "urls": {
            "googleMapsUrl": place.get("googleMapsUri", ""),
            "websiteUrl": place.get("websiteUri", "")
        },
        "reviews": {
            "rating": place.get("rating"),
            "userRatingCount": place.get("userRatingCount"),
        },
        "priceRange": place.get("priceRange"),
        "priceLevel": place.get("priceLevel"),
        "openingHours": {
            "current": {
                "openNow": place.get("currentOpeningHours", {}).get("openNow"),
                "weekdayDescriptions": place.get("currentOpeningHours", {}).get("weekdayDescriptions"),
                "nextOpenTime": place.get("currentOpeningHours", {}).get("nextOpenTime"),
                "nextCloseTime": place.get("currentOpeningHours", {}).get("nextCloseTime"),
            },
            "regular": {
                "openNow": place.get("regularOpeningHours", {}).get("openNow"),
                "weekdayDescriptions": place.get("regularOpeningHours", {}).get("weekdayDescriptions"),
                "nextOpenTime": place.get("regularOpeningHours", {}).get("nextOpenTime"),
                "nextCloseTime": place.get("regularOpeningHours", {}).get("nextCloseTime"),
            },
        },
        "accessibilityOptions": place.get("accessibilityOptions", {})
    }
    if include_dining_options:
        placeData["diningOptions"] = {
            "dineIn": place.get("dineIn"),
            "servesBeer": place.get("servesBeer"),
            "servesCocktails": place.get("servesCocktails"),
            "servesWine": place.get("servesWine"),
            "servesVegetarianFood": place.get("servesVegetarianFood"),
            "servesBreakfast": place.get("servesBreakfast"),
            "servesCoffee": place.get("servesCoffee"),
            "servesBrunch": place.get("servesBrunch"),
            "servesLunch": place.get("servesLunch"),
            "servesDinner": place.get("servesDinner"),
            "servesDessert": place.get("servesDessert")
        }
    if include_amenities:
        placeData["amenities"] = {
            "allowsDogs": place.get("allowsDogs"),
            "goodForChildren": place.get("goodForChildren"),
            "goodForGroups": place.get("goodForGroups"),
            "liveMusic": place.get("liveMusic"),
            "outdoorSeating": place.get("outdoorSeating"),
            "evChargeOptions": place.get("evChargeOptions", {}),
            "parkingOptions": place.get("parkingOptions", {}),
            "paymentOptions": place.get("paymentOptions", {})
        }
    return placeData
            

def _format_place_info(data: dict) -> dict:
    """Extended formatter for get_place_info which has richer type/summary fields."""
    base = _format_place(data, include_dining_options=True, include_amenities=True)
    # Override type with richer get_place_info fields
    base["type"] = {
        "primaryType": data.get("primaryType", ""),
        "primaryTypeName": data.get("primaryTypeDisplayName", {}).get("text", ""),
        "types": data.get("types", []),
    }
    editorial = data.get("editorialSummary", {}).get("text", "") or ""
    generative = data.get("generativeSummary", {}).get("overview", {}).get("text", "") or ""
    combined = editorial + generative
    base["placeSummaries"] = {
        "summary": combined[:_SUMMARY_MAX_CHARS],
        "neighborhoodSummary": (
            data.get("neighborhoodSummary", {})
            .get("overview", {})
            .get("content", {})
            .get("text", "")
        )[:_SUMMARY_MAX_CHARS]
    }
    _review_summary_raw = data.get("reviewSummary", {}).get("text", "") or ""
    if isinstance(_review_summary_raw, dict):
        _review_summary_raw = _review_summary_raw.get("text", "") or ""
    base["reviews"]["reviewSummary"] = str(_review_summary_raw)[:_SUMMARY_MAX_CHARS]
    base["phoneNumber"] = data.get("internationalPhoneNumber", "")
    return base


# Full set of valid Google Places API v1 primary types, resolved once at
# module load from the `GooglePlaceType` Literal in `constants.py`. Kept as
# a frozenset for O(1) membership checks during input validation.
#
# The Literal itself is NOT exposed to Gemini as an enum anymore: the
# `included_types` / `excluded_types` parameters use `List[str]` in the
# tool schema so Gemini's constrained decoder doesn't have to stay inside
# a 280-member enum (the old shape was a common MALFORMED_FUNCTION_CALL
# trigger). We instead validate each entry at runtime and return an
# actionable error with a sample of valid types if the model guesses wrong.
_VALID_PLACE_TYPES: frozenset[str] = frozenset(get_args(GooglePlaceType))

# Places API
async def search_places(query: Annotated[str, Field(description="The general or specific text query string to search for real-world places.")], 
                        include_dining_options: Annotated[Optional[bool], Field(description="(Optional) Whether to include dining options like serves beer, cocktails, wine, vegetarian food, breakfast, brunch, lunch, dinner, dessert in the search results. Try to keep it false to save cost and use get_place_info after finalizing the place to get all these details.", default=False)],
                        include_amenities: Annotated[Optional[bool], Field(description="(Optional) Whether to include amenities like allows dogs, good for children, good for groups, live music, outdoor seating, ev charge options, parking options, payment options in the search results. Try to keep it false to save cost and use get_place_info after finalizing the place to get all these details.", default=False)],
                        max_results: Annotated[int, Field(ge=1, le=10, description="The maximum number of results to fetch for the current page (min 1, max 10).", default=5)],
                        next_page_token: Annotated[Optional[str], Field(description="The next page token to continue the search from and get the next page of results. Optional. If provided, the search will continue from the next page.", default=None)],
                        place_index: Annotated[Optional[int], Field(description="(Optional) The index of the place to return from the search results for the current page.", default=0)],
                        timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['search_places'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    cache_key = await generate_cache_key("search_places", {"query": query.lower().strip(), "include_dining_options": include_dining_options, "include_amenities": include_amenities, "max_results": max_results, "next_page_token": next_page_token})
    cache_value = await retrieve_api_cache(cache_key, expires_in=7)

    # Context-aware SKU: jumps to "Atmosphere" variant when dining/amenity
    # field masks are requested. Skip on cache hit so repeat queries don't
    # burn the low 1,000/month Places quota.
    resolved_sku = resolve_search_places_sku(
        include_dining_options=include_dining_options,
        include_amenities=include_amenities,
    )
    try:
        await get_rate_limiter().consume(resolved_sku, cache_hit=bool(cache_value))
    except RateLimitExceeded as exc:
        return tool_error(
            f"Monthly quota exhausted for SKU '{exc.sku}'.",
            fix_hint=f"Do not retry. Skip this place search and proceed with what you have. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

    field_mask = GoogleFieldMasks["places"]["textSearch"]
    if include_dining_options:
        field_mask += "," + ",".join(_DINING_OPTIONS_FIELD_MASKS)
    if include_amenities:
        field_mask += "," + ",".join(_AMENITIES_FIELD_MASKS)
    
    url = "https://places.googleapis.com/v1/places:searchText"
    body = {
        "textQuery": query,
        "maxResultCount": max_results,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }
    if next_page_token:
        body["pageToken"] = next_page_token

    try:
        if cache_value:
            data = cache_value.get("places", [])
        else:
            client = get_http_client()
            response = await client.post(url, json=body, headers=headers, timeout=timeout_seconds)
            if response.status_code >= 400:
                return tool_error(
                    "Text place search failed upstream.",
                    fix_hint="5xx responses are transient — retry once. 4xx typically means the query was invalid; simplify or rephrase and retry.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            data = response.json()
            await insert_api_cache(cache_key, {"places": data})

        page_length = len(data.get("places", []))
        if page_length == 0:
            return tool_error(
                "No places matched the query.",
                fix_hint="Rephrase the query to be broader (e.g. use the city name alongside the feature). If you supplied a next_page_token, drop it and start fresh.",
            )
        if place_index >= page_length:
            return tool_error(
                f"`place_index` {place_index} is out of range.",
                fix_hint=f"This page has {page_length} place(s); choose `place_index` in [0, {page_length - 1}]. Use `nextIndex` / `nextPageToken` from a previous response to paginate.",
                extra={"page_length": page_length},
            )
        
        place = data.get("places", [])[place_index]
        return {
            "place": _format_place(place, include_dining_options, include_amenities),
            "nextPageToken": data.get("nextPageToken", None),
            "hasNext": len(data.get("places", [])) > place_index + 1,
            "nextIndex": place_index + 1 if len(data.get("places", [])) > place_index + 1 else None,
        }

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Text place search raised an unexpected error.",
            fix_hint="Retry once with the same query. If it fails again, rephrase the query.",
            extra={"exception": str(e)},
        )

async def search_places_nearby(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the central location as a float.")], 
                               lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the central location as a float.")], 
                               included_types: Annotated[List[str], Field(description="List of Google Places API v1 primary types to include (e.g. 'restaurant', 'tourist_attraction', 'museum', 'park', 'hotel', 'subway_station'). Each must be a valid Places v1 primary type; the tool returns an actionable error listing valid options if any entry is unknown.")],
                               radius: Annotated[float, Field(ge=10.0, le=50000.0, description="The search radius in meters around the specified location.", default=500)], 
                               include_dining_options: Annotated[Optional[bool], Field(description="(Optional) Whether to include dining options like serves beer, cocktails, wine, vegetarian food, breakfast, brunch, lunch, dinner, dessert in the search results. Try to keep it false to save cost and use get_place_info after finalizing the place to get all these details.", default=False)],
                               include_amenities: Annotated[Optional[bool], Field(description="(Optional) Whether to include amenities like allows dogs, good for children, good for groups, live music, outdoor seating, ev charge options, parking options, payment options in the search results. Try to keep it false to save cost and use get_place_info after finalizing the place to get all these details.", default=False)],
                               max_results: Annotated[int, Field(ge=10, le=20, description="The maximum number of results to fetch for the search (min 10, max 20).", default=20)],
                               rank_preference: Annotated[Literal["POPULARITY", "DISTANCE"], Field(description="The preference determining how the returned places are ranked.", default="POPULARITY")],
                               excluded_types: Annotated[Optional[List[str]], Field(description="Optional list of Google Places API v1 primary types to explicitly exclude. Same allowed values as `included_types`.", default=None)],
                               place_index: Annotated[int, Field(description="The index of the place to return from the search results fetched.", default=0)],
                               timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['search_places_nearby'])]) -> Dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    # Validate every supplied place type against the full GooglePlaceType
    # set. The model no longer sees the enum in its schema (see module
    # docstring), so it may occasionally guess an invalid string — we
    # return a crisp, actionable error it can self-correct from.
    invalid_included = [t for t in (included_types or []) if t not in _VALID_PLACE_TYPES]
    invalid_excluded = [t for t in (excluded_types or []) if t not in _VALID_PLACE_TYPES]
    if invalid_included or invalid_excluded:
        return {
            "error": "Invalid Google Places API v1 type(s) supplied.",
            "invalid_included_types": invalid_included,
            "invalid_excluded_types": invalid_excluded,
            "fix_hint": (
                "Call search_places_nearby again with only valid Google Places "
                "API v1 primary types. Common travel-focused values are listed "
                "in `valid_types_sample`; the tool prompt has the full set."
            ),
            "valid_types_sample": _PLACE_TYPE_SAMPLE,
        }

    cache_key = await generate_cache_key("search_places_nearby", {"lat": lat, "lng": lng, "included_types": included_types, "radius": radius, "include_dining_options": include_dining_options, "include_amenities": include_amenities, "max_results": max_results, "rank_preference": rank_preference, "excluded_types": excluded_types})
    cache_value = await retrieve_api_cache(cache_key, expires_in=7)

    # Context-aware SKU + cache-aware consume.
    resolved_sku = resolve_search_places_nearby_sku(
        include_dining_options=include_dining_options,
        include_amenities=include_amenities,
    )
    try:
        await get_rate_limiter().consume(resolved_sku, cache_hit=bool(cache_value))
    except RateLimitExceeded as exc:
        return tool_error(
            f"Monthly quota exhausted for SKU '{exc.sku}'.",
            fix_hint=f"Do not retry. Skip this nearby search. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

    field_mask = GoogleFieldMasks["places"]["nearbySearch"]
    if include_dining_options:
        field_mask += "," + ",".join(_DINING_OPTIONS_FIELD_MASKS)
    if include_amenities:
        field_mask += "," + ",".join(_AMENITIES_FIELD_MASKS)
    
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
        "X-Goog-FieldMask": field_mask,
    }
    try:
        if cache_value:
            data = cache_value.get("places", [])
        else:
            client = get_http_client()
            response = await client.post(url, json=body, headers=headers, timeout=timeout_seconds)
            if response.status_code >= 400:
                return tool_error(
                    "Nearby place search failed upstream.",
                    fix_hint="5xx responses are transient — retry once. 4xx often means one of the `included_types`/`excluded_types` is invalid, the radius is out of range (10..50000m), or coordinates are malformed.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            data = response.json()
            await insert_api_cache(cache_key, {"places": data})

        page_length = len(data.get("places", []))
        if page_length == 0:
            return tool_error(
                "No places found in this radius for the supplied types.",
                fix_hint="Try a larger `radius`, relax `included_types`, or drop `excluded_types`. If the lat/lng is over ocean or an unpopulated area, move it closer to a populated place.",
            )
        if place_index >= page_length:
            return tool_error(
                f"`place_index` {place_index} is out of range.",
                fix_hint=f"This page has {page_length} place(s); choose `place_index` in [0, {page_length - 1}].",
                extra={"page_length": page_length},
            )
        
        place = data.get("places", [])[place_index]
        return {
            "place": _format_place(place, include_dining_options, include_amenities),
            "hasNext": len(data.get("places", [])) > place_index + 1,
            "nextIndex": place_index + 1 if len(data.get("places", [])) > place_index + 1 else None,
            }
     

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Nearby place search raised an unexpected error.",
            fix_hint="Retry once. If it fails again, broaden the radius or relax the type filter.",
            extra={"exception": str(e)},
        )

async def get_place_info(place_id: Annotated[str, Field(description="The Google Place ID of the place to get information about. Must come from a previous search_places / search_places_nearby result.")],
                         timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_place_info'])]) -> dict:
    if not api_key:
        return tool_error(
            "Google Maps API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    cache_key = await generate_cache_key("get_place_info", {"place_id": place_id})
    cache_value = await retrieve_api_cache(cache_key, expires_in=31)

    # `get_place_info` always returns the full atmosphere field mask, so it
    # always bills the "Enterprise + Atmosphere" SKU.
    try:
        await get_rate_limiter().consume(
            SKU["places_place_details_enterprise_atmosphere"],
            cache_hit=bool(cache_value),
        )
    except RateLimitExceeded as exc:
        return tool_error(
            f"Monthly quota exhausted for SKU '{exc.sku}'.",
            fix_hint=f"Do not retry. Proceed without detailed place info. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

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
            client = get_http_client()
            response = await client.get(url, headers=headers, timeout=timeout_seconds)
            if response.status_code >= 400:
                return tool_error(
                    "Place info lookup failed upstream.",
                    fix_hint="Verify `place_id` is a valid Google Place ID obtained from search_places / search_places_nearby. 5xx is transient — retry once.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            data = response.json()
            if data: 
                await insert_api_cache(cache_key, {"place": data})

        if not data:
            return tool_error(
                "No place info returned for this Place ID.",
                fix_hint="Verify the Place ID is recent and accurate. Consider calling search_places again to get a fresh ID.",
            )
        
        return {"place": _format_place_info(data)}
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Place info lookup raised an unexpected error.",
            fix_hint="Retry once with the same `place_id`. If it fails again, re-fetch the Place ID via search_places.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_places.__doc__ = (PROMPTS_DIR / "search_places.md").read_text()
search_places_nearby.__doc__ = (PROMPTS_DIR / "search_places_nearby.md").read_text()
get_place_info.__doc__ = (PROMPTS_DIR / "get_place_info.md").read_text()