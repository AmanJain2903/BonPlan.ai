import asyncio
from fastmcp import FastMCP
from fastmcp.tools import Tool

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

# Ground Transportation Tools
from app.agent.mcp_server.tools.car_rental import search_rental_cars

# Accommodations Tools    
from app.agent.mcp_server.tools.accommodations import search_hotels


# This name will be visible to the LLM/Agent
mcp = FastMCP("BonPlan_MCP_Server")

# Timezone Tools
get_current_timestamp_tool = Tool.from_function(
    get_current_timestamp,
    name="get_current_timestamp"
)
mcp.add_tool(get_current_timestamp_tool)

convert_utc_string_to_timestamp_tool = Tool.from_function(
    convert_utc_string_to_timestamp,
    name="convert_utc_string_to_timestamp"
)
mcp.add_tool(convert_utc_string_to_timestamp_tool)

convert_timestamp_to_utc_string_tool = Tool.from_function(
    convert_timestamp_to_utc_string,
    name="convert_timestamp_to_utc_string"
)
mcp.add_tool(convert_timestamp_to_utc_string_tool)  

convert_target_local_time_to_utc_tool = Tool.from_function(
    convert_target_local_time_to_utc,
    name="convert_target_local_time_to_utc"
)
mcp.add_tool(convert_target_local_time_to_utc_tool)

get_timezone_tool = Tool.from_function(
    get_timezone,
    name="get_timezone"
)
mcp.add_tool(get_timezone_tool)

# Air Quality Tools
get_current_air_quality_tool = Tool.from_function(
    get_current_air_quality,
    name="get_current_air_quality"
)
mcp.add_tool(get_current_air_quality_tool)

get_air_quality_forecast_tool = Tool.from_function(
    get_air_quality_forecast,
    name="get_air_quality_forecast"
)
mcp.add_tool(get_air_quality_forecast_tool)

# Weather Tools
get_current_weather_tool = Tool.from_function(
    get_current_weather,
    name="get_current_weather"
)
mcp.add_tool(get_current_weather_tool)

get_daily_forecast_tool = Tool.from_function(
    get_daily_forecast,
    name="get_daily_forecast"
)
mcp.add_tool(get_daily_forecast_tool)

get_hourly_forecast_tool = Tool.from_function(
    get_hourly_forecast,
    name="get_hourly_forecast"
)
mcp.add_tool(get_hourly_forecast_tool)

# Geocoding Tools
get_coordinates_tool = Tool.from_function(
    get_coordinates,
    name="get_coordinates"
)
mcp.add_tool(get_coordinates_tool)

get_address_tool = Tool.from_function(
    get_address,
    name="get_address"
)
mcp.add_tool(get_address_tool)

get_optimal_route_tool = Tool.from_function(
    get_optimal_route,
    name="get_optimal_route"
)
mcp.add_tool(get_optimal_route_tool)

# Places Tools
search_places_tool = Tool.from_function(
    search_places,
    name="search_places"
)
mcp.add_tool(search_places_tool)

search_places_nearby_tool = Tool.from_function(
    search_places_nearby,
    name="search_places_nearby"
)
mcp.add_tool(search_places_nearby_tool)

get_place_info_tool = Tool.from_function(
    get_place_info,
    name="get_place_info"
)
mcp.add_tool(get_place_info_tool)

# Routes Tools
get_route_tool = Tool.from_function(
    get_route,
    name="get_route"
)
mcp.add_tool(get_route_tool)

get_route_matrix_tool = Tool.from_function(
    get_route_matrix,
    name="get_route_matrix"
)
mcp.add_tool(get_route_matrix_tool)

# Web Search Tools
search_web_tool = Tool.from_function(
    search_web,
    name="search_web"
)
mcp.add_tool(search_web_tool)

get_content_from_url_tool = Tool.from_function(
    get_content_from_url,
    name="get_content_from_url"
)
mcp.add_tool(get_content_from_url_tool)

# Flights Tools
get_country_code_tool = Tool.from_function(
    get_country_code,
    name="get_country_code"
)
mcp.add_tool(get_country_code_tool)

get_airports_and_codes_tool = Tool.from_function(
    get_airports_and_codes,
    name="get_airports_and_codes"
)
mcp.add_tool(get_airports_and_codes_tool)

search_flights_tool = Tool.from_function(
    search_flights,
    name="search_flights"
)
mcp.add_tool(search_flights_tool)

search_multi_city_flights_tool = Tool.from_function(
    search_multi_city_flights,
    name="search_multi_city_flights"
)
mcp.add_tool(search_multi_city_flights_tool)

get_next_flights_tool = Tool.from_function(
    get_next_flights,
    name="get_next_flights"
)
mcp.add_tool(get_next_flights_tool)

# Ground Transportation Tools
search_rental_cars_tool = Tool.from_function(
    search_rental_cars,
    name="search_rental_cars"
)
mcp.add_tool(search_rental_cars_tool)

# Accommodations Tools
search_hotels_tool = Tool.from_function(
    search_hotels,
    name="search_hotels"
)
mcp.add_tool(search_hotels_tool)


if __name__ == "__main__":
    # Standard I/O execution for MCP servers
    # This allows the LangGraph agent to call these tools as if they were local functions
    mcp.run()