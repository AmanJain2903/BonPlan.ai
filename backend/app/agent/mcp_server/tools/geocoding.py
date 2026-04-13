import requests
from typing import Dict, Annotated, Tuple, Optional, List
from pydantic import Field, BaseModel
from app.core.config import settings
import pathlib
from app.agent.mcp_server.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
import math
import itertools

api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED

class Location(BaseModel):
    addressOrName: Annotated[str, Field(description="The address or name of the location.")]
    lat: Annotated[Optional[float], Field(description="The latitude of the location.", default=None)]
    lng: Annotated[Optional[float], Field(description="The longitude of the location.", default=None)]

def haversineDistance(point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
    lat1, lon1 = point1
    lat2, lon2 = point2
    R = 6371 # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Geocoding API
def get_coordinates(address: Annotated[str, Field(description="The formal physical address or general city name to convert to absolute lat/lng coordinates.")]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    if not address:
        return {"error": "Address is required"}
    
    cache_key = generate_cache_key("get_coordinates", {"address": address.lower().strip()})
    cache_value = retrieve_api_cache(cache_key, expires_in=31)

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

    try:
        if cache_value:
            data = cache_value
        else:
            response = requests.get(url, params=params, timeout=5)
            if not response.ok:
                return {"error": f"Geocoding API error: {response.status_code} {response.text}"}
            data = response.json()
            if data["status"] != "OK":
                return {"error": f"Geocoding failed with status: {data.get('status', 'Unknown error')}"}
            insert_api_cache(cache_key, data)


        result = data["results"][0]
        if not result or not result["geometry"]["location"]:
            return {"error": "Geocoding failed with status: No results found"}
        
        return {
            "address": result.get("formatted_address", ""),
            "lat": result.get("geometry", {}).get("location", {}).get("lat", None),
            "lng": result.get("geometry", {}).get("location", {}).get("lng", None),
            "place_id": result.get("place_id", None)
        }
        
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def get_address(lat: Annotated[float, Field(ge=-90.0, le=90.0, description="The precise latitude of the location as a float.")],
                lng: Annotated[float, Field(ge=-180.0, le=180.0, description="The precise longitude of the location as a float.")]) -> Dict:
    if not api_key:
        return {"error": "Google API key not configured"}
    
    if not lat or not lng:
        return {"error": "Latitude and longitude are required"}
    
    cache_key = generate_cache_key("get_address", {"lat": lat, "lng": lng})
    cache_value = retrieve_api_cache(cache_key, expires_in=31)
        
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": api_key
    }
    
    try:
        if cache_value:
            data = cache_value
        else:
            response = requests.get(url, params=params, timeout=5)
            if not response.ok:
                return {"error": f"Geocoding API error: {response.status_code} {response.text}"}
            data = response.json()
            if data["status"] != "OK":
                return {"error": f"Geocoding failed with status: {data.get('status', 'Unknown error')}"}
            insert_api_cache(cache_key, data)
        
        result = data["results"][0]
        if not result or not result["formatted_address"]:
            return {"error": "Geocoding failed with status: No results found"}  
        return {"address": result.get("formatted_address", "")}
        
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def get_optimal_route(origin: Annotated[Location, Field(description="The origin location.")], destinations: Annotated[List[Location], Field(description="The list of destinations.")]) -> Dict:
    if not origin:
        return {"error": "An origin is required to calculate a route."}

    if not destinations or len(destinations) == 0:
        return {"error": "At least one destination is required to calculate a route."}
    
    if not origin.lat or not origin.lng:
        originCoordinates = get_coordinates(origin.addressOrName)
        origin.lat = originCoordinates["lat"]
        origin.lng = originCoordinates["lng"]
    for destination in destinations:
        if not destination.lat or not destination.lng:
            destinationCoordinates = get_coordinates(destination.addressOrName)
            destination.lat = destinationCoordinates["lat"]
            destination.lng = destinationCoordinates["lng"]
    
    cache_key = generate_cache_key("get_optimal_route", {"origin": origin.model_dump(), "destinations": [destination.model_dump() for destination in destinations]})
    cache_value = retrieve_api_cache(cache_key, expires_in=31)
    if cache_value:
        return cache_value

    best_sequence = []
    min_total_distance = float('inf')

    # Generate every possible order of visiting the destinations
    # Since we always start and end at the same origin, we only permute the middle
    for permutation in itertools.permutations(destinations):
        current_distance = 0
        current_path = [origin] + list(permutation) + [origin]
        for i in range(len(current_path) - 1):
            p1 = (current_path[i].lat, current_path[i].lng)
            p2 = (current_path[i+1].lat, current_path[i+1].lng)
            current_distance += haversineDistance(p1, p2)

        if current_distance < min_total_distance:
            min_total_distance = current_distance
            best_sequence = current_path
        
    route_names = [loc.addressOrName for loc in best_sequence]
    
    returnData = {
        "optimalSequence": [loc.model_dump() for loc in best_sequence],
        "totalDistanceKm": round(min_total_distance, 2),
        "totalDistanceMiles": round(min_total_distance * 0.621371, 2),
        "sequenceSummary": " -> ".join(route_names),
        "explanation": f"The most efficient route to start at {origin.addressOrName} and visit all {len(destinations)} cities and return to {origin.addressOrName} covers approximately {round(min_total_distance)} km."
    }
    insert_api_cache(cache_key, returnData)
    return returnData


PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_coordinates.__doc__ = (PROMPTS_DIR / "get_coordinates.md").read_text()
get_address.__doc__ = (PROMPTS_DIR / "get_address.md").read_text()
get_optimal_route.__doc__ = (PROMPTS_DIR / "get_optimal_route.md").read_text()