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
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
import traceback

rapid_api_key = settings.RAPID_API_KEY

class Passengers(BaseModel):
    adults: Annotated[int, Field(description="The number of adults (12 years or older) to search the flights for.", default=1)]
    children: Annotated[int, Field(description="The number of children (2-11 years old) to search the flights for.", default=0)]
    infant_on_lap: Annotated[int, Field(description="The number of infants (under 2 years old) to search the flights for. The infant will be on the lap of an adult.", default=0)]
    infant_in_seat: Annotated[int, Field(description="The number of infants (under 2 years old) to search the flights for. The infant will be in a seat.", default=0)]

class FlightLeg(BaseModel):
    departure_id: Annotated[str, Field(description="The departure airport code in IATA format to search the flights for.")]
    arrival_id: Annotated[str, Field(description="The arrival airport code in IATA format to search the flights for.")]
    date: Annotated[str, Field(description="The date departure for the flights to search for in format YYYY-MM-DD.")]

async def format_date_time(date_time: str, airport_name: str) -> Dict:
    if not date_time or not airport_name:
        return {
            "original_local_time": None,
            "utc_string": None,
            "utc_timestamp": None,
        }
    coordinates = await get_coordinates(airport_name, timeout_seconds=TIMEOUTS['get_coordinates'])
    timezone = await get_timezone(coordinates.get("lat"), coordinates.get("lng"), timestamp=None, timeout_seconds=TIMEOUTS['get_timezone'])
    dateTime = date_time.split(" ")
    date = dateTime[0].split("-")
    time = dateTime[1].split(":")
    dateTimeString = f"{date[0]}-{date[1].zfill(2)}-{date[2].zfill(2)}T{time[0].zfill(2)}:{time[1].zfill(2)}:00"
    return convert_target_local_time_to_utc(dateTimeString, timezone.get("timeZoneId").get("value"))

async def format_flight_data(data: Dict, flight_type: str) -> Dict:
    departureTime = None
    arrivalTime = None
    flightItinerary = []
    layovers = []

    for flight in data.get("flights", []):
        departure = await format_date_time(flight.get("departure_airport", {}).get("time", None), flight.get("departure_airport", {}).get("airport_name", None))
        arrival = await format_date_time(flight.get("arrival_airport", {}).get("time", None), flight.get("arrival_airport", {}).get("airport_name", None))
        departureTimeObject = {
            "localTimeString_departureLocation": departure.get("original_local_time", None),
            "utcTimeString": departure.get("utc_string", None),
            "timestamp": departure.get("utc_timestamp", None),
        }
        arrivalTimeObject = {
            "localTimeString_arrivalLocation": arrival.get("original_local_time", None),
            "utcTimeString": arrival.get("utc_string", None),
            "timestamp": arrival.get("utc_timestamp", None),
        }
        if not departureTime:
            departureTime = departureTimeObject
        elif departureTimeObject.get("timestamp") and departureTime.get("timestamp") > departureTimeObject.get("timestamp"):
            departureTime = departureTimeObject
        if not arrivalTime:
            arrivalTime = arrivalTimeObject
        elif arrivalTimeObject.get("timestamp") and arrivalTime.get("timestamp") < arrivalTimeObject.get("timestamp"):
            arrivalTime = arrivalTimeObject

        flightItinerary.append({
            "departureAirport": {
                "airportCode": flight.get("departure_airport", {}).get("airport_code", None),
                "airportName": flight.get("departure_airport", {}).get("airport_name", None),
            },
            "arrivalAirport": {
                "airportCode": flight.get("arrival_airport", {}).get("airport_code", None),
                "airportName": flight.get("arrival_airport", {}).get("airport_name", None),
            },
            "departureTime": departureTimeObject,
            "arrivalTime": arrivalTimeObject,
            "duration": {
                "durationInMinutes": flight.get("duration", {}).get("raw", None)
            },
            "airline": {
                "airlineName": flight.get("airline", None),
                "airlineLogo": flight.get("airline_logo", None),
                "flightNumber": flight.get("flight_number", None)
            }
        })
    
    if data.get("layovers", None):
        for stop in data.get("layovers", []):
            layovers.append({
                "airportCode": stop.get("airport_code", None),
                "airportName": stop.get("airport_name", None),
                "cityName": stop.get("city", None),
                "duration": {
                    "durationInMinutes": stop.get("duration", None)
                }
            })

    returnData = {
        "departureTime": departureTime,
        "arrivalTime": arrivalTime,
        "durationInMinutes": data.get("duration", {}).get("raw", None),
        "priceInUSD": data.get("price", None),
        "flightItinerary": flightItinerary,
        "layovers": layovers,
        "flight_type": flight_type
    }
    if data.get("booking_token", None):
        cache_key = generate_cache_key("booking_token", {"booking_token": data.get("booking_token", None)})
        cache_value = await retrieve_api_cache(cache_key, expires_in=365)
        if not cache_value:
            await insert_api_cache(cache_key, {"booking_token": data.get("booking_token", None)})
        returnData["bookingToken"] = cache_key
    if data.get("next_token", None):
        cache_key = generate_cache_key("next_token", {"next_token": data.get("next_token", None)})
        cache_value = await retrieve_api_cache(cache_key, expires_in=365)
        if not cache_value:
            await insert_api_cache(cache_key, {"next_token": data.get("next_token", None)})
        returnData["nextToken"] = cache_key
    return returnData

async def _assemble_flight_results(
    itineraries: Dict, flight_type: str, return_type: Optional[str] = "topFlights"
) -> Dict:

    return_data: Dict = {}
    topFlights = []
    otherFlights = []
    if return_type == "topFlights":
        if itineraries.get("topFlights", []):
            for flight in itineraries.get("topFlights", []):
                topFlights.append(await format_flight_data(flight, flight_type))
            return_data["topFlights"] = topFlights
        else:
            for flight in itineraries.get("otherFlights", []):
                otherFlights.append(await format_flight_data(flight, flight_type))
            return_data["note"] = "No top flights found. Returning other flights instead." if otherFlights else "No flights found."
            return_data["otherFlights"] = otherFlights
    elif return_type == "otherFlights":
        if itineraries.get("otherFlights", []):
            for flight in itineraries.get("otherFlights", []):
                otherFlights.append(await format_flight_data(flight, flight_type))
            return_data["otherFlights"] = otherFlights
        else:
            return_data["note"] = "No other flights found."
            return_data["otherFlights"] = otherFlights
    else:
        if itineraries.get("topFlights", []):
            for flight in itineraries.get("topFlights", []):
                topFlights.append(await format_flight_data(flight, flight_type))
            return_data["topFlights"] = topFlights
        if itineraries.get("otherFlights", []):
            for flight in itineraries.get("otherFlights", []):
                otherFlights.append(await format_flight_data(flight, flight_type))
            return_data["otherFlights"] = otherFlights
        if not topFlights and not otherFlights:
            return_data["note"] = "No flights found."
    return return_data

# RapidAPI Google Flights API
async def get_country_code(country_name: Annotated[str, Field(description="The name of the country to get the code for. Just the country name, no other text like 'country' or 'code' or 'state' etc.")],
                           timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_country_code'])]) -> Dict:
    if not country_name:
        return tool_error(
            "`country_name` is required.",
            fix_hint="Retry with a non-empty country name (e.g. 'France', 'Japan').",
        )
    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )
    country_name = country_name.lower().strip()
    url = "https://google-flights2.p.rapidapi.com/api/v1/getLocations"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    cache_key = generate_cache_key("get_country_code", {"type": "all_codes"})
    cache_value = await retrieve_api_cache(cache_key, expires_in=365)
    if cache_value:
        country_codes = cache_value
    else:
        try:
            client = get_http_client()
            response = await client.get(url, headers=headers, timeout=timeout_seconds)
            if response.status_code >= 400:
                return tool_error(
                    "Failed to fetch country-code table.",
                    fix_hint="5xx responses are transient — retry once. 4xx means the provider rejected the call; proceed without flight data.",
                    status_code=response.status_code,
                    extra={"upstream": response.text[:300]},
                )
            raw_data = response.json()
            if not raw_data.get("data", []) or len(raw_data.get("data", [])) == 0:
                return tool_error(
                    "Provider returned no country-code entries.",
                    fix_hint="This should not normally happen. Retry once; if it fails, proceed without flight data.",
                )
            raw_country_codes = raw_data.get("data", [])
            country_codes = {}
            for raw_country_code in raw_country_codes:
                country_codes[raw_country_code.get("country_name", "").lower().strip()] = raw_country_code.get("country_code", "")
            if country_codes:
                await insert_api_cache(cache_key, country_codes)
        except httpx.TimeoutException:
            return tool_error(
                f"Tool timeout after {timeout_seconds} seconds.",
                fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
            )
        except Exception as e:
            return tool_error(
                "Unexpected error while fetching country codes.",
                fix_hint="Retry once with the same arguments. If it fails again, proceed without flight data.",
                extra={"exception": str(e)},
            )
    country_code = country_codes.get(country_name, "")
    if not country_code:
        return tool_error(
            f"No country code found for '{country_name}'.",
            fix_hint="Verify spelling (e.g. use 'United States' not 'USA', 'United Kingdom' not 'UK'). Retry with the exact English country name.",
        )
    return {"country_code": country_code}

async def get_airports_and_codes(query: Annotated[str, Field(description="The query to search the airports for. Can be airport name, place name, city name, etc. Preferably use the airport name as the query.")],
                     country_code: Annotated[Optional[str], Field(description="Optional. The country code to search the airports for. If not provided, all airports will be searched.", default=None)],
                     timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_airports_and_codes'])]) -> Dict:
    if not query:
        return tool_error(
            "`query` is required.",
            fix_hint="Retry with a non-empty query (airport name, place name, or city name).",
        )
    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )
    query = query.lower().strip()
    url = f"https://google-flights2.p.rapidapi.com/api/v1/searchAirport"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    params = {
        "query": query
    }
    if country_code:
        params["country_code"] = country_code
    cache_key = generate_cache_key("get_airports_and_codes", params)
    cache_value = await retrieve_api_cache(cache_key, expires_in=365)
    if cache_value:
        return cache_value
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Airport search failed upstream.",
                fix_hint="Verify the query spelling and, if supplied, that `country_code` is a valid two-letter code. 5xx responses are transient — retry once.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        output = {}
        for item in data.get("data", []):
            if item.get("type") == "airport":
                if item.get("id", "") != "":
                    output[item.get("title", "")] = {
                        "airport_code": item.get("id", ""),
                        "distance": item.get("distance", None),
                    }
            elif item.get("type") == "other":
                for listItem in item.get("list", []):
                    if listItem.get("type") == "airport" and listItem.get("id", "") != "":
                        output[listItem.get("title", "")] = {
                            "airport_code": listItem.get("id", ""),
                            "distance": listItem.get("distance", None),
                        }
        if output:
            await insert_api_cache(cache_key, output)
            return output
        else:
            return tool_error(
                "No airports found for this query.",
                fix_hint="Retry with a broader query (e.g. the nearest major city name instead of a precise airport name), or remove the `country_code` filter.",
            )
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Airport search raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, broaden the query or proceed without flight data.",
            extra={"exception": str(e)},
        )

async def search_flights(departure_id: Annotated[str, Field(description="The departure airport code to search the flights for.")],
                   arrival_id: Annotated[str, Field(description="The arrival airport code to search the flights for.")],
                   outbound_date: Annotated[str, Field(description="The departure date to search the flights for. According to the timezone of the departure airport. Think of it as the wall clock time of the departure airport. In format YYYY-MM-DD")],
                   passengers: Annotated[Passengers, Field(description="The passengers to search the flights for. Default is 1 adult.")],
                   return_date: Annotated[Optional[str], Field(description="(Optional) The return date to search the flights for. According to the timezone of the arrival airport. Think of it as the wall clock time of the arrival airport. In format YYYY-MM-DD", default=None)],
                   travel_class: Annotated[Optional[Literal["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]], Field(description="(Optional) The travel class to search the flights for.", default="ECONOMY")],
                   search_type: Annotated[Optional[Literal["best", "cheap"]], Field(description="(Optional) The type of flight search to perform.", default=None)],
                   return_type: Annotated[Optional[Literal["topFlights", "otherFlights", "all"]], Field(description="(Optional) The type of flights to return.", default="topFlights")],
                   timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['search_flights'])]) -> Dict:

    flight_type = "ONE_WAY"

    if not departure_id or not arrival_id or not outbound_date:
        return tool_error(
            "Required parameters are missing.",
            fix_hint="Retry with `departure_id`, `arrival_id`, and `outbound_date` (YYYY-MM-DD) all populated. Use get_airports_and_codes first if you don't know the IATA codes.",
        )

    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )

    url = "https://google-flights2.p.rapidapi.com/api/v1/searchFlights"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    passengers_dict = passengers.model_dump()
    params = {
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "travel_class": travel_class,
        "adults": max(passengers_dict.get("adults", 1), 1),
        "children": passengers_dict.get("children", 0),
        "infant_on_lap": passengers_dict.get("infant_on_lap", 0),
        "infant_in_seat": passengers_dict.get("infant_in_seat", 0),
    }
    if return_date:
        params["return_date"] = return_date
        flight_type = "ROUND_TRIP"
    if search_type:
        params["search_type"] = search_type
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Flight search failed upstream.",
                fix_hint="Verify IATA codes are valid and the outbound_date is in the future (and return_date is after outbound_date, if provided). 5xx is transient — retry once.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        topFlights = []
        otherFlights = []
        itineraries = data.get("data", {}).get("itineraries", {})
        return await _assemble_flight_results(itineraries, flight_type, return_type)
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Flight search raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without flight data.",
            extra={"exception": str(e)},
        )

async def search_multi_city_flights(legs: Annotated[List[FlightLeg], Field(description="The list of flight legs to search the flights for.")],
                               passengers: Annotated[Passengers, Field(description="The passengers to search the flights for. Default is 1 adult.")],
                               travel_class: Annotated[Optional[Literal["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]], Field(description="(Optional) The travel class to search the flights for.", default="ECONOMY")],
                               search_type: Annotated[Optional[Literal["best", "cheap"]], Field(description="(Optional) The type of flight search to perform.", default=None)],
                               return_type: Annotated[Optional[Literal["topFlights", "otherFlights", "all"]], Field(description="(Optional) The type of flights to return.", default="topFlights")],
                               timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['search_multi_city_flights'])]) -> Dict:
    flight_type = "MULTI_CITY"
    if not legs:
        return tool_error(
            "At least one flight leg is required.",
            fix_hint="Retry with `legs` as a list of at least one {departure_id, arrival_id, date} object.",
        )
    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )
    url = "https://google-flights2.p.rapidapi.com/api/v1/searchMultiCityFlights"

    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    passengers_dict = passengers.model_dump()
    body = {
        "legs": [leg.model_dump() for leg in legs],
        "adults": max(passengers_dict.get("adults", 1), 1),
        "children": passengers_dict.get("children", 0),
        "infant_on_lap": passengers_dict.get("infant_on_lap", 0),
        "infant_in_seat": passengers_dict.get("infant_in_seat", 0),
        "travel_class": travel_class,
    }
    if search_type:
        body["search_type"] = search_type
    try:
        client = get_http_client()
        response = await client.post(url, headers=headers, json=body, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Multi-city flight search failed upstream.",
                fix_hint="Verify every leg has valid IATA codes and a future date, and that legs are in chronological order. 5xx is transient — retry once.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        topFlights = []
        otherFlights = []
        itineraries = data.get("data", {}).get("itineraries", {})
        return await _assemble_flight_results(itineraries, flight_type, return_type)
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Multi-city flight search raised an unexpected error.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without flight data.",
            extra={"exception": str(e)},
        )

async def get_next_flights(next_token: Annotated[str, Field(description="The next token to get the next flights for. Used to get the subsequent leg of round-trip or multi-city flights. Only pass this if you have received a nextToken from a previous call to search_flights, search_multi_city_flights, or get_next_flights.")],
                     return_type: Annotated[Optional[Literal["topFlights", "otherFlights", "all"]], Field(description="(Optional) The type of flights to return.", default="topFlights")],
                     timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_next_flights'])]) -> Dict:
    flight_type = "This tool is only used for round trip or multi-city flights. So the flight type is always ROUND_TRIP or MULTI_CITY. Use the flight type returned from the previous call to search_flights or search_multi_city_flights tool to determine the flight type."
    if not next_token:
        return tool_error(
            "`next_token` is required.",
            fix_hint="Only call get_next_flights after search_flights / search_multi_city_flights returns a `nextToken`. Pass that exact token as `next_token`.",
        )
    next_token_data = await retrieve_api_cache(next_token)
    if not next_token_data or not next_token_data.get("next_token", None):
        return tool_error(
            "`next_token` is invalid or expired.",
            fix_hint="Retry with a fresh `next_token` by re-running the previous call to search_flights or search_multi_city_flights tool. The tokens are very short lived and will expire after a few minutes so call this tool immediately after getting the next token.",
        )
    next_token = next_token_data.get("next_token", None)
    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )
    url = "https://google-flights2.p.rapidapi.com/api/v1/getNextFlights"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    params = {
        "next_token": next_token
    }
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Next-flights lookup failed upstream.",
                fix_hint="The `next_token` may have expired or the upstream is temporarily unavailable. Retry once; if it still fails, do another search_flights call to get a fresh token.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        if not data.get("data", {}):
            return tool_error(
                "No results returned from the upstream.",
                fix_hint="The `next_token` may have expired or the upstream is temporarily unavailable. Retry once; by getting a fresh next token by re-running the previous call to search_flights or search_multi_city_flights tool. The tokens are very short lived and will expire after a few minutes so call this tool immediately after getting the next token.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        topFlights = []
        otherFlights = []
        itineraries = data.get("data", {}).get("itineraries", {})
        return await _assemble_flight_results(itineraries, flight_type, return_type)
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Next-flights lookup raised an unexpected error.",
            fix_hint="Retry once with the same token. If it fails again, do a fresh search_flights call to obtain a new nextToken.",
            extra={"exception": str(e)},
        )

async def get_flight_booking_details(booking_token: Annotated[str, Field(description="The booking token to get the booking URL for. Must be a valid booking token returned from search_flights or search_multi_city_flights or get_next_flights tool.")],
                                     timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_flight_booking_details'])]) -> Dict:
    if not booking_token:
        return tool_error(
            "`booking_token` is required.",
            fix_hint="Only call get_flight_booking_url after search_flights or search_multi_city_flights or get_next_flights returns a `booking_token`. Pass that exact token as `booking_token`.",
        )
    booking_token_data = await retrieve_api_cache(booking_token)
    if not booking_token_data or not booking_token_data.get("booking_token", None):
        return tool_error(
            "`booking_token` is invalid or expired.",
            fix_hint="Retry with a fresh `booking_token` by re-running the previous call to search_flights or search_multi_city_flights or get_next_flights tool. The tokens are very short lived and will expire after a few minutes so call this tool immediately after getting the booking token.",
        )
    booking_token = booking_token_data.get("booking_token", None)
    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )
    url = "https://google-flights2.p.rapidapi.com/api/v1/getBookingDetails"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    params = {
        "booking_token": booking_token
    }
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Booking details lookup failed upstream.",
                fix_hint="The `booking_token` may have expired or the upstream is temporarily unavailable. Retry once; if it still fails, do a fresh search_flights call to obtain a new booking token. If still fails, proceed without the booking URL.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        if not data or not data.get("data", []):
            return tool_error(
                "No results returned from the upstream.",
                fix_hint="The `booking_token` may have expired or the upstream is temporarily unavailable. Retry once; by getting a fresh booking token by re-running the previous call to search_flights or search_multi_city_flights or get_next_flights tool. The tokens are very short lived and will expire after a few minutes so call this tool immediately after getting the booking token.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        packages = []
        for package in data.get("data", []):
            cache_key = generate_cache_key("token", {"token": package.get("token", None)})
            await insert_api_cache(cache_key, {"token": package.get("token", None)})
            token = cache_key
            packages.append({
                "cabin": package.get("cabin", ""),
                "website": package.get("website", ""),
                "priceInUSD": package.get("price", ""),
                "baggageOptions": (package.get("meta") or {}).get("baggage", []),
                "fareType": (package.get("meta") or {}).get("fare_type", ""),
                "token": token
            })
        return {
            "booking_options": packages
        }
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except httpx.RequestError as e:
        return tool_error(
            "Transient network error while communicating with the upstream.",
            fix_hint="Network errors are commonly transient. Retry calling this tool exactly ONCE more. If it fails again, proceed without the booking data.",
            extra={"exception_type": str(type(e)), "exception": str(e)}
        )
    except Exception as e:
        return tool_error(
            "Booking details lookup raised an unexpected error.",
            fix_hint="Retry once with the same token. If it fails again, do a fresh search_flights call to obtain a new booking token. If still fails, proceed without the booking URL.",
            extra={"exception": str(e)},
        )

async def get_flight_booking_url(token: Annotated[str, Field(description="The token to get the booking URL for. Must be a valid token returned from get_flight_booking_details tool.")],
                                 timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_flight_booking_url'])]) -> Dict:
    if not token:
        return tool_error(
            "`token` is required.",
            fix_hint="Only call get_flight_booking_url after get_flight_booking_details returns a `token`. Pass that exact token as `token`.",
        )
    token_data = await retrieve_api_cache(token)
    if not token_data or not token_data.get("token", None):
        return tool_error(
            "`token` is invalid or expired.",
            fix_hint="Retry with a fresh `token` by re-running the previous call to get_flight_booking_details tool. The tokens are very short lived and will expire after a few minutes so call this tool immediately after getting the token.",
        )
    token = token_data.get("token", None)
    if not rapid_api_key:
        return tool_error(
            "Flights provider is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without flight data.",
        )
    url = "https://google-flights2.p.rapidapi.com/api/v1/getBookingURL"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    params = {
        "token": token
    }
    cache_key = generate_cache_key("get_flight_booking_url", params)
    cache_value = await retrieve_api_cache(cache_key, expires_in=365)
    if cache_value:
        return {
            "booking_url": cache_value.get("booking_url", "")
        }
    try:
        client = get_http_client()
        response = await client.get(url, headers=headers, params=params, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Booking URL lookup failed upstream.",
                fix_hint="The `token` may have expired or the upstream is temporarily unavailable. Retry once; if it still fails, do a fresh get_flight_booking_details call to obtain a new token. If still fails, proceed without the booking URL.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        if not data:
            return tool_error(
                "No results returned from the upstream.",
                fix_hint="The `token` may have expired or the upstream is temporarily unavailable. Retry once; by getting a fresh token by re-running the previous call to get_flight_booking_details tool. The tokens are very short lived and will expire after a few minutes so call this tool immediately after getting the token.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        await insert_api_cache(cache_key, {"booking_url": data.get("data", "")})
        return {
            "booking_url": data.get("data", "")
        }
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except httpx.RequestError as e:
        return tool_error(
            "Transient network error while communicating with the upstream.",
            fix_hint="Network errors are commonly transient. Retry calling this tool exactly ONCE more. If it fails again, proceed without the booking URL.",
            extra={"exception_type": str(type(e)), "exception": str(e)}
        )
    except Exception as e:
        return tool_error(
            "Booking URL lookup raised an unexpected error.",
            fix_hint="Retry once with the same token. If it fails again, do a fresh get_flight_booking_details call to obtain a new token. If still fails, proceed without the booking URL.",
            extra={"exception": str(e)},
        )


PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_country_code.__doc__ = (PROMPTS_DIR / "get_country_code.md").read_text()
get_airports_and_codes.__doc__ = (PROMPTS_DIR / "get_airports_and_codes.md").read_text()
search_flights.__doc__ = (PROMPTS_DIR / "search_flights.md").read_text()
search_multi_city_flights.__doc__ = (PROMPTS_DIR / "search_multi_city_flights.md").read_text()
get_next_flights.__doc__ = (PROMPTS_DIR / "get_next_flights.md").read_text()
get_flight_booking_details.__doc__ = (PROMPTS_DIR / "get_flight_booking_details.md").read_text()
get_flight_booking_url.__doc__ = (PROMPTS_DIR / "get_flight_booking_url.md").read_text()



