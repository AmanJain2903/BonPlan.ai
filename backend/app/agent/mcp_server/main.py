from contextlib import asynccontextmanager
from typing import Callable

from fastmcp import FastMCP
from fastmcp.tools import Tool

from app.core.config import settings
from app.logging import get_mcp_logger
from app.utils.http import close_http_client

logger = get_mcp_logger("main")

# Timezone Tools
from app.agent.mcp_server.tools.timezone import get_current_timestamp
from app.agent.mcp_server.tools.timezone import convert_utc_string_to_timestamp
from app.agent.mcp_server.tools.timezone import convert_timestamp_to_utc_string
from app.agent.mcp_server.tools.timezone import convert_target_local_time_to_utc
from app.agent.mcp_server.tools.timezone import get_timezone

# Air Quality Tools
from app.agent.mcp_server.tools.air_quality import get_current_air_quality
from app.agent.mcp_server.tools.air_quality import get_air_quality_forecast

# Weather Tools
from app.agent.mcp_server.tools.weather import get_current_weather
from app.agent.mcp_server.tools.weather import get_daily_forecast
from app.agent.mcp_server.tools.weather import get_hourly_forecast

# Geocoding Tools
from app.agent.mcp_server.tools.geocoding import get_coordinates
from app.agent.mcp_server.tools.geocoding import get_address
from app.agent.mcp_server.tools.geocoding import get_optimal_route

# Places Tools
from app.agent.mcp_server.tools.places import search_places
from app.agent.mcp_server.tools.places import search_places_nearby
from app.agent.mcp_server.tools.places import get_place_info

# Routes Tools
from app.agent.mcp_server.tools.routes import get_route
from app.agent.mcp_server.tools.route_matrix import get_route_matrix

# Web Search Tools
from app.agent.mcp_server.tools.web_search import search_web
from app.agent.mcp_server.tools.web_search import get_content_from_url

# Flights Tools
from app.agent.mcp_server.tools.flights import get_country_code
from app.agent.mcp_server.tools.flights import get_airports_and_codes
from app.agent.mcp_server.tools.flights import search_flights
from app.agent.mcp_server.tools.flights import search_multi_city_flights
from app.agent.mcp_server.tools.flights import get_next_flights
from app.agent.mcp_server.tools.flights import get_flight_booking_details
from app.agent.mcp_server.tools.flights import get_flight_booking_url

# Ground Transportation Tools
from app.agent.mcp_server.tools.car_rental import search_rental_cars

# Accommodations Tools    
from app.agent.mcp_server.tools.accommodations import search_hotels
from app.agent.mcp_server.tools.accommodations import get_hotel_booking_url

# Currency Tools
from app.agent.mcp_server.tools.currency import get_supported_currencies
from app.agent.mcp_server.tools.currency import convert_currency_to_USD


@asynccontextmanager
async def mcp_lifespan(_server):
    logger.info("MCP service starting", service=settings.MCP_NAME, version=settings.MCP_VERSION)
    try:
        yield
    finally:
        await close_http_client()
        logger.info("MCP service shutdown complete")


_TOOL_REGISTRY: list[tuple[str, Callable[..., object]]] = [
    ("get_current_timestamp", get_current_timestamp),
    ("convert_utc_string_to_timestamp", convert_utc_string_to_timestamp),
    ("convert_timestamp_to_utc_string", convert_timestamp_to_utc_string),
    ("convert_target_local_time_to_utc", convert_target_local_time_to_utc),
    ("get_timezone", get_timezone),
    ("get_current_air_quality", get_current_air_quality),
    ("get_air_quality_forecast", get_air_quality_forecast),
    ("get_current_weather", get_current_weather),
    ("get_daily_forecast", get_daily_forecast),
    ("get_hourly_forecast", get_hourly_forecast),
    ("get_coordinates", get_coordinates),
    ("get_address", get_address),
    ("get_optimal_route", get_optimal_route),
    ("search_places", search_places),
    ("search_places_nearby", search_places_nearby),
    ("get_place_info", get_place_info),
    ("get_route", get_route),
    ("get_route_matrix", get_route_matrix),
    ("search_web", search_web),
    ("get_content_from_url", get_content_from_url),
    ("get_country_code", get_country_code),
    ("get_airports_and_codes", get_airports_and_codes),
    ("search_flights", search_flights),
    ("search_multi_city_flights", search_multi_city_flights),
    ("get_next_flights", get_next_flights),
    ("get_flight_booking_details", get_flight_booking_details),
    ("get_flight_booking_url", get_flight_booking_url),
    ("search_rental_cars", search_rental_cars),
    ("search_hotels", search_hotels),
    ("get_hotel_booking_url", get_hotel_booking_url),
    ("get_supported_currencies", get_supported_currencies),
    ("convert_currency_to_USD", convert_currency_to_USD),
]


def _build_mcp_server() -> FastMCP:
    server = FastMCP(
        settings.MCP_NAME,
        version=settings.MCP_VERSION,
        lifespan=mcp_lifespan,
    )
    for tool_name, fn in _TOOL_REGISTRY:
        server.add_tool(Tool.from_function(fn, name=tool_name))
    return server


# This name is visible to the agent during MCP initialization.
mcp = _build_mcp_server()


if __name__ == "__main__":
    # Standard I/O execution for MCP servers
    # This allows the LangGraph agent to call these tools as if they were local functions
    logger.info("MCP server starting (stdio)")
    try:
        mcp.run()
    except Exception:
        logger.exception("MCP server crashed")
        raise
    finally:
        logger.info("MCP server exited")
