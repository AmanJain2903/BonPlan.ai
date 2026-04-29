# backend/app/services/sku_resolver.py

"""
SKU resolution for the surgical rate limiter.

The same underlying MCP tool can bill different Google SKUs depending on its
arguments. For example:

- `get_route` charges "Routes: Compute Routes Essentials" when
  `routing_preference == "TRAFFIC_UNAWARE"` AND `optimize_waypoint_order` is
  False, but "Routes: Compute Routes Pro" otherwise.
- `search_places` charges the "Enterprise" SKU by default but jumps to
  "Enterprise + Atmosphere" the moment the caller opts into dining/amenity
  field masks.

This module centralises those rules so the decorator and the tools don't have
to encode branching logic inline.

Every SKU name returned here MUST match a row in the rate_limit_configs table.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from app.logging import get_rate_limiter_logger

logger = get_rate_limiter_logger("sku_resolver")

# --- canonical SKU slugs -----------------------------------------------------
#
# Keep these lowercased and underscore-separated — the rate_limit_configs table
# normalises SKU strings to lowercase on write and lookup.
SKU = {
    # Backend: simple (no arg branching)
    "timezone": "timezone",
    "geocoding": "geocoding",
    "weather_usage": "weather_usage",
    "air_quality_usage": "air_quality_usage",
    # Backend: routes (branching)
    "routes_compute_routes_essentials": "routes_compute_routes_essentials",
    "routes_compute_routes_pro": "routes_compute_routes_pro",
    "routes_compute_route_matrix_essentials": "routes_compute_route_matrix_essentials",
    "routes_compute_route_matrix_pro": "routes_compute_route_matrix_pro",
    # Backend: places (branching)
    "places_text_search_enterprise": "places_text_search_enterprise",
    "places_text_search_enterprise_atmosphere": "places_text_search_enterprise_atmosphere",
    "places_nearby_search_enterprise": "places_nearby_search_enterprise",
    "places_nearby_search_enterprise_atmosphere": "places_nearby_search_enterprise_atmosphere",
    "places_place_details_enterprise_atmosphere": "places_place_details_enterprise_atmosphere",
    "places_place_details_essentials_ids_only": "places_place_details_essentials_ids_only",
    "places_text_search_essentials_ids_only": "places_text_search_essentials_ids_only",
    "places_place_details_photos": "places_place_details_photos",
    # Frontend-reported SKUs (informational — cannot be enforced server-side,
    # but we seed them so the admin UI sees the quota baseline).
    "dynamic_maps": "dynamic_maps",
    "directions": "directions",
    "autocomplete_session_usage": "autocomplete_session_usage",
    "places_place_details_essentials": "places_place_details_essentials",
    "autocomplete_requests": "autocomplete_requests",
    # Third-party APIs and internal LLM SKUs.
    "serper_web_search": "serper_web_search",                # search_web tool
    "serper_content_parser": "serper_content_parser",        # get_content_from_url Gemini parse
    "google_flights": "google_flights",                      # all flights.py RapidAPI tools
    "booking_com": "booking_com",                            # all accommodations.py RapidAPI tools
    "exchange_rates": "exchange_rates",                      # currency.py RapidAPI tools
    "context_pruning": "context_pruning",                    # planner history-summarization Gemini call
    "planner_agent": "planner_agent",                        # each planner Gemini turn
    "conversation_agent": "conversation_agent",              # each conversation Gemini turn
    "editing_agent": "editing_agent",                        # each editing Gemini turn
}


# --- branching resolvers -----------------------------------------------------

def resolve_get_route_sku(**kwargs: Any) -> str:
    """
    `get_route` MCP tool.

    Per the SKU spec:
      - TRAFFIC_UNAWARE + optimize_waypoint_order=False => Essentials
      - otherwise                                       => Route Matrix Essentials
    """
    routing_preference = kwargs.get("routing_preference", "TRAFFIC_AWARE")
    optimize_waypoint_order = kwargs.get("optimize_waypoint_order", True)
    if routing_preference == "TRAFFIC_UNAWARE" and not optimize_waypoint_order:
        return SKU["routes_compute_routes_essentials"]
    return SKU["routes_compute_routes_pro"]


def resolve_get_route_matrix_sku(**kwargs: Any) -> str:
    """
    `get_route_matrix` MCP tool.

    Per the SKU spec:
      - TRAFFIC_UNAWARE     => Compute Routes Pro (5,000/mo)
      - not TRAFFIC_UNAWARE => Compute Route Matrix Pro (5,000/mo)
    """
    routing_preference = kwargs.get("routing_preference", "TRAFFIC_AWARE")
    if routing_preference == "TRAFFIC_UNAWARE":
        return SKU["routes_compute_route_matrix_essentials"]
    return SKU["routes_compute_route_matrix_pro"]


def resolve_search_places_sku(**kwargs: Any) -> str:
    include_dining = kwargs.get("include_dining_options", False)
    include_amenities = kwargs.get("include_amenities", False)
    if include_dining or include_amenities:
        return SKU["places_text_search_enterprise_atmosphere"]
    return SKU["places_text_search_enterprise"]


def resolve_search_places_nearby_sku(**kwargs: Any) -> str:
    include_dining = kwargs.get("include_dining_options", False)
    include_amenities = kwargs.get("include_amenities", False)
    if include_dining or include_amenities:
        return SKU["places_nearby_search_enterprise_atmosphere"]
    return SKU["places_nearby_search_enterprise"]


# --- registry (tool_name -> resolver) ----------------------------------------

SkuResolver = Callable[..., str]

TOOL_TO_SKU: dict[str, SkuResolver] = {
    "get_timezone": lambda **_: SKU["timezone"],
    "get_coordinates": lambda **_: SKU["geocoding"],
    "get_address": lambda **_: SKU["geocoding"],
    "get_current_weather": lambda **_: SKU["weather_usage"],
    "get_daily_forecast": lambda **_: SKU["weather_usage"],
    "get_hourly_forecast": lambda **_: SKU["weather_usage"],
    "get_current_air_quality": lambda **_: SKU["air_quality_usage"],
    "get_air_quality_forecast": lambda **_: SKU["air_quality_usage"],
    "get_route": resolve_get_route_sku,
    "get_route_matrix": resolve_get_route_matrix_sku,
    "search_places": resolve_search_places_sku,
    "search_places_nearby": resolve_search_places_nearby_sku,
    "get_place_info": lambda **_: SKU["places_place_details_enterprise_atmosphere"],
    # Third-party / internal SKUs (no arg branching).
    "search_web": lambda **_: SKU["serper_web_search"],
    "get_content_from_url": lambda **_: SKU["serper_content_parser"],
    "get_country_code": lambda **_: SKU["google_flights"],
    "get_airports_and_codes": lambda **_: SKU["google_flights"],
    "search_flights": lambda **_: SKU["google_flights"],
    "search_multi_city_flights": lambda **_: SKU["google_flights"],
    "get_next_flights": lambda **_: SKU["google_flights"],
    "get_flight_booking_details": lambda **_: SKU["google_flights"],
    "get_flight_booking_url": lambda **_: SKU["google_flights"],
    "search_hotels": lambda **_: SKU["booking_com"],
    "get_hotel_booking_url": lambda **_: SKU["booking_com"],
    "search_rental_cars": lambda **_: SKU["booking_com"],
    "get_supported_currencies": lambda **_: SKU["exchange_rates"],
    "convert_currency_to_USD": lambda **_: SKU["exchange_rates"],
    # Backend endpoints (not MCP tools, still go through consume())
    "get_destination_image_by_place_id": lambda **_: SKU["places_place_details_essentials_ids_only"],
    "get_destination_images_by_name": lambda **_: SKU["places_text_search_essentials_ids_only"],
    "build_proxy_url": lambda **_: SKU["places_place_details_photos"],
}


def resolve_sku(tool_name: str, **kwargs: Any) -> Optional[str]:
    resolver = TOOL_TO_SKU.get(tool_name)
    if resolver is None:
        logger.error("No SKU resolver found for tool", tool_name=tool_name, kwargs=kwargs)
        return None
    return resolver(**kwargs)
