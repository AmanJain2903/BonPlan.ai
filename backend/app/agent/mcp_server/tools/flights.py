import requests
from typing import Dict, Annotated, List, Optional, Literal
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.agent.mcp_server.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
from app.agent.mcp_server.tools.timezone import convert_target_local_time_to_utc, get_timezone
from app.agent.mcp_server.tools.geocoding import get_coordinates
import time
from datetime import datetime

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

def format_date_time(date_time: str, airport_name: str) -> Dict:
    if not date_time or not airport_name:
        return {
            "original_local_time": None,
            "utc_string": None,
            "utc_timestamp": None,
        }
    coordinates = get_coordinates(airport_name)
    timezone = get_timezone(coordinates.get("lat"), coordinates.get("lng"), timestamp=None)
    dateTime = date_time.split(" ")
    date = dateTime[0].split("-")
    time = dateTime[1].split(":")
    dateTimeString = f"{date[0]}-{date[1].zfill(2)}-{date[2].zfill(2)}T{time[0].zfill(2)}:{time[1].zfill(2)}:00"
    return convert_target_local_time_to_utc(dateTimeString, timezone.get("timeZoneId").get("value"))


def format_flight_data(data: Dict) -> Dict:
    departureTime = None
    arrivalTime = None
    duration = {
        "durationInMinutes": data.get("duration", {}).get("raw", None),
        "humanReadableDuration": data.get("duration", {}).get("text", None),
    }

    flightItinerary = []
    layovers = []

    for flight in data.get("flights", []):
        departure = format_date_time(flight.get("departure_airport", {}).get("time", None), flight.get("departure_airport", {}).get("airport_name", None))
        arrival = format_date_time(flight.get("arrival_airport", {}).get("time", None), flight.get("arrival_airport", {}).get("airport_name", None))
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
                "durationInMinutes": flight.get("duration", {}).get("raw", None),
                "humanReadableDuration": flight.get("duration", {}).get("text", None),
            },
            "airline": {
                "airlineName": flight.get("airline", None),
                "airlineLogo": flight.get("airline_logo", None),
                "flightNumber": flight.get("flight_number", None),
                "aircraft": flight.get("aircraft", None),
                "seat": flight.get("seat", None),
                "legroom": flight.get("legroom", None),
            },
            "extraInfo": flight.get("extensions", None),
        })
    
    if data.get("layovers", None):
        for stop in data.get("layovers", []):
            layovers.append({
                "airportCode": stop.get("airport_code", None),
                "airportName": stop.get("airport_name", None),
                "cityName": stop.get("city", None),
                "duration": {
                    "durationInMinutes": stop.get("duration", None),
                    "humanReadableDuration": stop.get("duration_label", None),
                }
            })

    returnData = {
        "departureTime": departureTime,
        "arrivalTime": arrivalTime,
        "duration": duration,
        "priceInUSD": data.get("price", None),
        "baggageOptions": data.get("bags", None),
        "flightItinerary": flightItinerary,
        "layovers": layovers
    }
    if data.get("booking_token", None):
        returnData["bookingToken"] = data.get("booking_token", None)
    if data.get("next_token", None):
        returnData["nextToken"] = data.get("next_token", None)
    return returnData

# RapidAPI Google Flights API
def get_country_code(country_name: Annotated[str, Field(description="The name of the country to get the code for. Just the country name, no other text like 'country' or 'code' or 'state' etc.")]) -> Dict:
    if not country_name:
        return {"error": "Country name is required"}
    if not rapid_api_key:
        return {"error": "RapidAPI key is required"}
    country_name = country_name.lower().strip()
    url = "https://google-flights2.p.rapidapi.com/api/v1/getLocations"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "google-flights2.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    cache_key = generate_cache_key("get_country_code", {"type": "all_codes"})
    cache_value = retrieve_api_cache(cache_key, expires_in=365)
    if cache_value:
        country_codes = cache_value
    else:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if not response.ok:
                return {"error": f"Failed to get available locations: {response.status_code} {response.text}"}
            raw_data = response.json()
            if not raw_data.get("data", []) or len(raw_data.get("data", [])) == 0:
                return {"error": "No country codes found"}
            raw_country_codes = raw_data.get("data", [])
            country_codes = {}
            for raw_country_code in raw_country_codes:
                country_codes[raw_country_code.get("country_name", "").lower().strip()] = raw_country_code.get("country_code", "")
            if country_codes:
                insert_api_cache(cache_key, country_codes)
        except Exception as e:
            return {"error": f"Failed to get available locations: {str(e)}"}
    country_code = country_codes.get(country_name, "")
    if not country_code:
        return {"error": "Country code not found"}
    return {"country_code": country_code}

def get_airports_and_codes(query: Annotated[str, Field(description="The query to search the airports for. Can be airport name, place name, city name, etc. Preferably use the airport name as the query.")],
                     country_code: Annotated[Optional[str], Field(description="Optional. The country code to search the airports for. If not provided, all airports will be searched.", default=None)]) -> Dict:
    if not query:
        return {"error": "Query is required"}
    if not rapid_api_key:
        return {"error": "RapidAPI key is required"}
    query = query.lower().strip()
    cache_key = generate_cache_key("get_airports_and_codes", {"query": query, "country_code": country_code})
    cache_value = retrieve_api_cache(cache_key, expires_in=365)
    if cache_value:
        return cache_value
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
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if not response.ok:
            return {"error": f"Failed to get airports and codes: {response.status_code} {response.text}"}
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
            insert_api_cache(cache_key, output)
            return output
        else:
            return {"error": "No airports found for the given query and country code"}
    except Exception as e:
        return {"error": f"Failed to get airports and codes: {str(e)}"}

def search_flights(departure_id: Annotated[str, Field(description="The departure airport code to search the flights for.")],
                   arrival_id: Annotated[str, Field(description="The arrival airport code to search the flights for.")],
                   outbound_date: Annotated[str, Field(description="The departure date to search the flights for. According to the timezone of the departure airport. Think of it as the wall clock time of the departure airport. In format YYYY-MM-DD")],
                   passengers: Annotated[Passengers, Field(description="The passengers to search the flights for. Default is 1 adult.")],
                   return_date: Annotated[Optional[str], Field(description="The return date to search the flights for. According to the timezone of the arrival airport. Think of it as the wall clock time of the arrival airport. In format YYYY-MM-DD", default=None)],
                   travel_class: Annotated[Optional[Literal["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]], Field(description="The travel class to search the flights for.", default="ECONOMY")],
                   search_type: Annotated[Optional[Literal["best", "cheap"]], Field(description="The type of flight search to perform.", default=None)],
                   return_type: Annotated[Optional[Literal["topFlights", "otherFlights", "all"]], Field(description="The type of flights to return.", default="topFlights")]) -> Dict:
    if not departure_id or not arrival_id or not outbound_date:
        return {"error": "Required parameters are missing"}
    
    if not rapid_api_key:
        return {"error": "RapidAPI key is required"}

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
    if search_type:
        params["search_type"] = search_type
    try:
        response = requests.get(url, headers=headers, params=params, timeout=45)
        if not response.ok:
            return {"error": f"Failed to search flights: {response.status_code} {response.text}"}
        data = response.json()
        topFlights = []
        otherFlights = []
        itineraries = data.get("data", {}).get("itineraries", {})
        for flight in itineraries.get("topFlights", []):
            topFlights.append(format_flight_data(flight))
        for flight in itineraries.get("otherFlights", []):
            otherFlights.append(format_flight_data(flight))
        returnData = {}
        if return_type == "topFlights":
            if topFlights:
                returnData["topFlights"] = topFlights
            else:
                returnData["Message"] = "No top flights found. Returning other flights instead."
                returnData["otherFlights"] = otherFlights
        elif return_type == "otherFlights":
            returnData["otherFlights"] = otherFlights
        elif return_type == "all":
            returnData["topFlights"] = topFlights
            returnData["otherFlights"] = otherFlights
        return returnData
    except Exception as e:
        return {"error": f"Failed to search flights: {str(e)}"}

def search_multi_city_flights(legs: Annotated[List[FlightLeg], Field(description="The list of flight legs to search the flights for.")],
                               passengers: Annotated[Passengers, Field(description="The passengers to search the flights for. Default is 1 adult.")],
                               travel_class: Annotated[Optional[Literal["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"]], Field(description="The travel class to search the flights for.", default="ECONOMY")],
                               search_type: Annotated[Optional[Literal["best", "cheap"]], Field(description="The type of flight search to perform.", default=None)],
                               return_type: Annotated[Optional[Literal["topFlights", "otherFlights", "all"]], Field(description="The type of flights to return.", default="topFlights")]) -> Dict:
    if not legs:
        return {"error": "At least one flight leg is required"}
    if not rapid_api_key:
        return {"error": "RapidAPI key is required"}
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
        response = requests.post(url, headers=headers, json=body, timeout=45)
        if not response.ok:
            return {"error": f"Failed to search multi-city flights: {response.status_code} {response.text}"}
        data = response.json()
        topFlights = []
        otherFlights = []
        itineraries = data.get("data", {}).get("itineraries", {})
        for flight in itineraries.get("topFlights", []):
            topFlights.append(format_flight_data(flight))
        for flight in itineraries.get("otherFlights", []):
            otherFlights.append(format_flight_data(flight))
        returnData = {}
        if return_type == "topFlights":
            if topFlights:
                returnData["topFlights"] = topFlights
            else:
                returnData["Message"] = "No top flights found. Returning other flights instead."
                returnData["otherFlights"] = otherFlights
        elif return_type == "otherFlights":
            returnData["otherFlights"] = otherFlights
        elif return_type == "all":
            returnData["topFlights"] = topFlights
            returnData["otherFlights"] = otherFlights
        return returnData
    except Exception as e:
        return {"error": f"Failed to search multi-city flights: {str(e)}"}

def get_next_flights(next_token: Annotated[str, Field(description="The next token to get the next flights for. Used to get the return leg of the flights if search_flights is called with return_date. Only pass this if you have received a nextToken from a previous call to search_flights.")],
                     return_type: Annotated[Optional[Literal["topFlights", "otherFlights", "all"]], Field(description="The type of flights to return.", default="topFlights")]) -> Dict:
    if not next_token:
        return {"error": "Next token is required"}
    if not rapid_api_key:
        return {"error": "RapidAPI key is required"}
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
        response = requests.get(url, headers=headers, params=params, timeout=45)
        if not response.ok:
            return {"error": f"Failed to get next flights: {response.status_code} {response.text}"}
        data = response.json()
        topFlights = []
        otherFlights = []
        itineraries = data.get("data", {}).get("itineraries", {})
        for flight in itineraries.get("topFlights", []):
            topFlights.append(format_flight_data(flight))
        for flight in itineraries.get("otherFlights", []):
            otherFlights.append(format_flight_data(flight))
        returnData = {}
        if return_type == "topFlights":
            if topFlights:
                returnData["topFlights"] = topFlights
            else:
                returnData["Message"] = "No top flights found. Returning other flights instead."
                returnData["otherFlights"] = otherFlights
        elif return_type == "otherFlights":
            returnData["otherFlights"] = otherFlights
        elif return_type == "all":
            returnData["topFlights"] = topFlights
            returnData["otherFlights"] = otherFlights
        return returnData
    except Exception as e:
        return {"error": f"Failed to get next flights: {str(e)}"}


PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_country_code.__doc__ = (PROMPTS_DIR / "get_country_code.md").read_text()
get_airports_and_codes.__doc__ = (PROMPTS_DIR / "get_airports_and_codes.md").read_text()
search_flights.__doc__ = (PROMPTS_DIR / "search_flights.md").read_text()
search_multi_city_flights.__doc__ = (PROMPTS_DIR / "search_multi_city_flights.md").read_text()
get_next_flights.__doc__ = (PROMPTS_DIR / "get_next_flights.md").read_text()


