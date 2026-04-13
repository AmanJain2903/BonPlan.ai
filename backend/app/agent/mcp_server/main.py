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
    name="get_current_timestamp",
    description=(
        "Returns the current Unix timestamp in seconds."
    ),
)
mcp.add_tool(get_current_timestamp_tool)

convert_utc_string_to_timestamp_tool = Tool.from_function(
    convert_utc_string_to_timestamp,
    name="convert_utc_string_to_timestamp",
    description=(
        "Converts a UTC ISO 8601 time string to a Unix timestamp in seconds."
    ),
)
mcp.add_tool(convert_utc_string_to_timestamp_tool)

convert_timestamp_to_utc_string_tool = Tool.from_function(
    convert_timestamp_to_utc_string,
    name="convert_timestamp_to_utc_string",
    description=(
        "Converts a Unix timestamp to a human-readable UTC ISO 8601 string."
    ),
)
mcp.add_tool(convert_timestamp_to_utc_string_tool)  

convert_target_local_time_to_utc_tool = Tool.from_function(
    convert_target_local_time_to_utc,
    name="convert_target_local_time_to_utc",
    description=(
        "Converts local time in a target timezone to an absolute UTC timestamp."
    ),
)
mcp.add_tool(convert_target_local_time_to_utc_tool)

get_timezone_tool = Tool.from_function(
    get_timezone,
    name="get_timezone",
    description=(
        "Retrieves timezone offsets and metadata for a specific lat/lng location."
    ),
)
mcp.add_tool(get_timezone_tool)

# Air Quality Tools
get_current_air_quality_tool = Tool.from_function(
    get_current_air_quality,
    name="get_current_air_quality",
    description=(
        "Fetches the current real-time Air Quality Index (AQI) for a location."
    ),
)
mcp.add_tool(get_current_air_quality_tool)

get_air_quality_forecast_tool = Tool.from_function(
    get_air_quality_forecast,
    name="get_air_quality_forecast",
    description=(
        "Forecasts AQI for a location up to 96 hours in the future."
    ),
)
mcp.add_tool(get_air_quality_forecast_tool)

# Weather Tools
get_current_weather_tool = Tool.from_function(
    get_current_weather,
    name="get_current_weather",
    description=(
        "Fetches current real-time weather conditions for a location."
    ),
)
mcp.add_tool(get_current_weather_tool)

get_daily_forecast_tool = Tool.from_function(
    get_daily_forecast,
    name="get_daily_forecast",
    description=(
        "Retrieves a 10-day daily weather forecast starting from the current date."
    ),
)
mcp.add_tool(get_daily_forecast_tool)

get_hourly_forecast_tool = Tool.from_function(
    get_hourly_forecast,
    name="get_hourly_forecast",
    description=(
        "Retrieves a 24-hour hour-by-hour weather forecast starting from the current time."
    ),
)
mcp.add_tool(get_hourly_forecast_tool)

# Geocoding Tools
get_coordinates_tool = Tool.from_function(
    get_coordinates,
    name="get_coordinates",
    description=(
        "Converts a plain-text address or city name into exact coordinates."
    ),
)
mcp.add_tool(get_coordinates_tool)

get_address_tool = Tool.from_function(
    get_address,
    name="get_address",
    description=(
        "Translates latitude and longitude coordinates into a readable physical address."
    ),
)
mcp.add_tool(get_address_tool)

get_optimal_route_tool = Tool.from_function(
    get_optimal_route,
    name="get_optimal_route",
    description=(
        "Calculates the most efficient route to visit a list of destinations from an origin."
    ),
)
mcp.add_tool(get_optimal_route_tool)

# Places Tools
search_places_tool = Tool.from_function(
    search_places,
    name="search_places",
    description=(
        "Searches for places worldwide using a simple global text query."
    ),
)
mcp.add_tool(search_places_tool)

search_places_nearby_tool = Tool.from_function(
    search_places_nearby,
    name="search_places_nearby",
    description=(
        "Discovers specific types of places strictly within a radius of a given coordinate."
    ),
)
mcp.add_tool(search_places_nearby_tool)

get_place_info_tool = Tool.from_function(
    get_place_info,
    name="get_place_info",
    description=(
        "Gets a less detailed information about a place using its Google Place ID."
    ),
)
mcp.add_tool(get_place_info_tool)

# Routes Tools
get_route_tool = Tool.from_function(
    get_route,
    name="get_route",
    description=(
        "Computes detailed routing, duration, and directions between points and waypoints."
    ),
)
mcp.add_tool(get_route_tool)

get_route_matrix_tool = Tool.from_function(
    get_route_matrix,
    name="get_route_matrix",
    description=(
        "Computes route status, routing, duration, and distance between multiple points and waypoints. Upto a total of 625 combinations of origins and destinations."
    ),
)
mcp.add_tool(get_route_matrix_tool)

# Web Search Tools
search_web_tool = Tool.from_function(
    search_web,
    name="search_web",
    description=(
        "Searches the web for information using a query."
    ),
)
mcp.add_tool(search_web_tool)

get_content_from_url_tool = Tool.from_function(
    get_content_from_url,
    name="get_content_from_url",
    description=(
        "Gets the content from a URL."
    ),
)
mcp.add_tool(get_content_from_url_tool)

# Flights Tools
get_country_code_tool = Tool.from_function(
    get_country_code,
    name="get_country_code",
    description=(
        "Gets the country code for a given country name."
    ),
)
mcp.add_tool(get_country_code_tool)

get_airports_and_codes_tool = Tool.from_function(
    get_airports_and_codes,
    name="get_airports_and_codes",
    description=(
        "Gets the airports and codes for a given query and optionally a country code. Can be airport name, place name, city name, etc."
    ),
)
mcp.add_tool(get_airports_and_codes_tool)

search_flights_tool = Tool.from_function(
    search_flights,
    name="search_flights",
    description=(
        "Searches for flights between two airports on a given departure and/or return date."
    ),
)
mcp.add_tool(search_flights_tool)

search_multi_city_flights_tool = Tool.from_function(
    search_multi_city_flights,
    name="search_multi_city_flights",
    description=(
        "Searches for flights between multiple airports in a single journey."
    ),
)
mcp.add_tool(search_multi_city_flights_tool)

get_next_flights_tool = Tool.from_function(
    get_next_flights,
    name="get_next_flights",
    description=(
        "Gets the next flights for a given next token. Used to get the return leg of the flights if search_flights is called with return_date. Only pass this if you have received a nextToken from a previous call to search_flights."
    ),
)
mcp.add_tool(get_next_flights_tool)

# Ground Transportation Tools
search_rental_cars_tool = Tool.from_function(
    search_rental_cars,
    name="search_rental_cars",
    description=(
        "Searches for rental cars between two coordinates on a given pickup and dropoff date and time."
    ),
)
mcp.add_tool(search_rental_cars_tool)

# Accommodations Tools
search_hotels_tool = Tool.from_function(
    search_hotels,
    name="search_hotels",
    description=(
        "Searches for hotels in a given location and date range."
    ),
)
mcp.add_tool(search_hotels_tool)


if __name__ == "__main__":
    # Standard I/O execution for MCP servers
    # This allows the LangGraph agent to call these tools as if they were local functions
    mcp.run()