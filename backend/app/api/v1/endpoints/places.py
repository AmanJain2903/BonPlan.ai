# backend/app/api/v1/endpoints/places.py

"""
This file contains the places endpoints for the v1 version of the API.
"""

from fastapi import APIRouter, Query

from app.core.config import settings
from app.utils.http import get_http_client
from app.api.caching import retrieve_api_cache, insert_api_cache, generate_cache_key

router = APIRouter()

API_KEY = settings.GOOGLE_MAPS_API_KEY
BASE_URL = "https://places.googleapis.com/v1"
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Default generic beautiful image fallback to prevent frontend UI breakage
FALLBACK_IMAGE = settings.FALLBACK_IMAGE

maxWidth = 1080


@router.get("/destination-image-by-place-id")
async def get_destination_image_by_place_id(place_id: str = Query(..., description="Google Place ID"), count: int = Query(5, description="Number of images to return"), min_ratio: float = Query(1.5, description="Minimum ratio of width to height for landscape images")):
    if not API_KEY:
        return {"image_urls": [FALLBACK_IMAGE]}
    cache_key = await generate_cache_key("get_destination_image_by_place_id", {"place_id": place_id})
    cached_value = await retrieve_api_cache(cache_key, expires_in=1)
    if cached_value:
        photos = cached_value.get("photos", [])
    else:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": "photos"
        }
        client = get_http_client()
        place_resp = await client.get(f"{BASE_URL}/places/{place_id}", headers=headers, timeout=10)
        if place_resp.status_code != 200:
            return {"image_urls": [FALLBACK_IMAGE]}
        data = place_resp.json()
        photos = data.get("photos", [])
        await insert_api_cache(cache_key, {"photos": photos})
    if not photos:
        return {"image_urls": [FALLBACK_IMAGE]}
    photo_urls = []
    for photo in photos:
        width = photo.get("widthPx", 0)
        height = photo.get("heightPx", 0)
        if height > 0:
            if width / height >= min_ratio:
                resource_name = photo.get("name")
                media_url = f"{BASE_URL}/{resource_name}/media?key={API_KEY}&maxWidthPx={maxWidth}"
                photo_urls.append(media_url)
    return {"image_urls": photo_urls[:count]}

@router.get("/destination-images-by-name")
async def get_destination_images_by_name(destination: str = Query(..., description="Destination city/place name"), count: int = Query(5, description="Number of images to return"), min_ratio: float = Query(1.5, description="Minimum ratio of width to height for landscape images")):
    if not API_KEY:
        return {"image_urls": [FALLBACK_IMAGE]}
    cache_key = await generate_cache_key("get_destination_images_by_name", {"destination": destination.lower()})
    cached_value = await retrieve_api_cache(cache_key, expires_in=1)
    if cached_value:
        all_photos = cached_value.get("photos", [])
    else:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": "places.id,places.displayName,places.photos"
        }
        payload = {
        "textQuery": destination,
        "maxResultCount": 1 ## This is for searching for the place
        }
        client = get_http_client()
        place_resp = await client.post(SEARCH_URL, headers=headers, json=payload, timeout=10)
        if place_resp.status_code != 200:
            return {"image_urls": [FALLBACK_IMAGE], "error": "Failed to search for the destination"}
        results = place_resp.json().get("places", [])
        if not results:
            return {"image_urls": [FALLBACK_IMAGE], "error": "No results found for the destination"}
        target_place = results[0]
        all_photos = target_place.get("photos", [])
        await insert_api_cache(cache_key, {"photos": all_photos})
    photo_urls = []
    for photo in all_photos:
        width = photo.get("widthPx", 0)
        height = photo.get("heightPx", 0)
        if height > 0:
            if width / height >= min_ratio:
                resource_name = photo.get("name")
                media_url = f"{BASE_URL}/{resource_name}/media?key={API_KEY}&maxWidthPx={maxWidth}"
                photo_urls.append(media_url)
    return {"image_urls": photo_urls[:count]}