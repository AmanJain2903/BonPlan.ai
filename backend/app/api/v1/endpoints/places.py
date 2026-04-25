# backend/app/api/v1/endpoints/places.py

"""
This file contains the places endpoints for the v1 version of the API.

Includes a server-side image proxy that downloads Google Places photos once,
caches them in PostgreSQL, and serves them to the frontend. This prevents
repeated Google API billing on every browser render.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.core.config import settings
from app.utils.http import get_http_client
from app.api.caching import retrieve_api_cache, insert_api_cache, generate_cache_key
from app.database.database import Session
from app.database.models.placePhotoCache import PlacePhotoCache
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import SKU

from fastapi import HTTPException
from PIL import Image
from io import BytesIO
import os

router = APIRouter()

API_KEY = settings.GOOGLE_MAPS_API_KEY
BACKEND_URL = settings.BACKEND_URL
BASE_URL = "https://places.googleapis.com/v1"
SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Fallback image path
_FALLBACK_IMAGE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "static", "fallbackImage.jpg"
)

maxWidth = 1080

# Photo cache TTL: 30 days (max allowed by Google ToS)
PHOTO_CACHE_TTL_DAYS = 31

async def _is_bright_enough(image_bytes: bytes, dark_threshold=40, light_threshold=230) -> bool:
    """Checks if an image is within acceptable brightness bounds."""
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            # Convert to grayscale to get luminance (L)
            # L = 0.299R + 0.587G + 0.114B (Standard PIL conversion)
            img = img.convert('RGB')
            # Resize to 10x10 to average out quickly
            img = img.resize((10, 10))
            pixels = list(img.getdata())
            luminance_scores = [
                (0.2126 * r + 0.7152 * g + 0.0722 * b) 
                for (r, g, b) in pixels
            ]
            avg_luminance = sum(luminance_scores) / len(luminance_scores)
            
            return dark_threshold <= avg_luminance <= light_threshold
    except Exception:
        return True

async def _build_proxy_url(resource_name: str, db: Session) -> str:
    """Build a URL that points to our own proxy endpoint instead of Google."""
    result = (await db.execute(
        select(PlacePhotoCache).where(PlacePhotoCache.resource_name == resource_name)
    )).scalar_one_or_none()

    if result:
        if result.created_at and result.created_at < datetime.now(timezone.utc) - timedelta(days=PHOTO_CACHE_TTL_DAYS):
            # Expired — delete and re-fetch
            await db.delete(result)
            await db.commit()
            result = None

    if result:
        imageBytes = result.image_data
    else:
        if not API_KEY:
            return None
        # Places Photos SKU: billed per Google Places Media API call. DB-cached
        # photos skip this path entirely so we only consume on genuine fetches.
        try:
            await get_rate_limiter().consume(SKU["places_place_details_photos"])
        except RateLimitExceeded:
            # Fail-soft for photos — return None so the caller falls back to a
            # placeholder rather than hard-erroring on quota exhaustion.
            return settings.FALLBACK_IMAGE
        google_url = f"{BASE_URL}/{resource_name}/media?key={API_KEY}&maxWidthPx={maxWidth}"
        client = get_http_client()
        try:
            google_resp = await client.get(google_url, timeout=15, follow_redirects=True)
        except Exception:
            return None
        if google_resp.status_code != 200:
            return None
        imageBytes = google_resp.content
        content_type = google_resp.headers.get("content-type", "image/jpeg")
        try:
            new_entry = PlacePhotoCache(
                resource_name=resource_name,
                image_data=imageBytes,
                content_type=content_type,
            )
            db.add(new_entry)
            await db.commit()
        except Exception:
            await db.rollback()
    if not imageBytes:
        return None
    if not await _is_bright_enough(imageBytes):
        return None
    return f"{BACKEND_URL}/api/v1/places/place-photo/{resource_name}"
    
@router.get("/place-photo/{resource_name:path}")
async def get_place_photo(resource_name: str):
    """
    Image proxy endpoint. Serves a cached photo binary from the database,
    or fetches it from Google once and caches it for up to 30 days.

    The frontend uses this URL in <img> tags instead of hitting Google directly.
    """
    async with Session() as db:
        result = (await db.execute(
            select(PlacePhotoCache).where(PlacePhotoCache.resource_name == resource_name)
        )).scalar_one_or_none()

        if result:
            return Response(
                content=result.image_data,
                media_type=result.content_type,
                headers={
                    "Cache-Control": f"public, max-age={PHOTO_CACHE_TTL_DAYS * 86400}, immutable",
                    "X-Photo-Cache": "HIT",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        else:
            with open(_FALLBACK_IMAGE_PATH, "rb") as f:
                imageBytes = f.read()
            return Response(
                content=imageBytes,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": f"public, max-age={PHOTO_CACHE_TTL_DAYS * 86400}, immutable",
                    "X-Photo-Cache": "MISS",
                    "Access-Control-Allow-Origin": "*",
                },
            )

@router.get("/destination-image-by-place-id")
async def get_destination_image_by_place_id(place_id: str = Query(..., description="Google Place ID"), count: int = Query(5, description="Number of images to return"), min_ratio: float = Query(1.5, description="Minimum ratio of width to height for landscape images")):
    if not place_id or place_id == "" or place_id == "N/A":
        return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Place ID is required"}
    cache_key = await generate_cache_key("get_destination_image_by_place_id", {"place_id": place_id})
    cached_value = await retrieve_api_cache(cache_key, expires_in=31)

    # SKU is IDs-only field mask => unlimited per spec; consume() short-circuits,
    # but we still register the call for observability.
    try:
        await get_rate_limiter().consume(
            SKU["places_place_details_essentials_ids_only"],
            cache_hit=bool(cached_value),
        )
    except RateLimitExceeded as exc:
        return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Rate limit exceeded."}

    if cached_value:
        photos = cached_value.get("photos", [])
    else:
        if not API_KEY:
            return {"image_urls": [settings.FALLBACK_IMAGE]}
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": "photos"
        }
        client = get_http_client()
        place_resp = await client.get(f"{BASE_URL}/places/{place_id}", headers=headers, timeout=10)
        if place_resp.status_code != 200:
            return {"image_urls": [settings.FALLBACK_IMAGE]}
        data = place_resp.json()
        photos = data.get("photos", [])
        await insert_api_cache(cache_key, {"photos": photos})
    if not photos:
        return {"image_urls": [settings.FALLBACK_IMAGE]}
    photo_urls = []
    async with Session() as db:
        for photo in photos:
            if len(photo_urls) >= count:
                break
            width = photo.get("widthPx", 0)
            height = photo.get("heightPx", 0)
            if height > 0:
                if width / height >= min_ratio:
                    resource_name = photo.get("name")
                    # Return proxy URL instead of direct Google URL
                    media_url = await _build_proxy_url(resource_name, db)
                    if media_url:
                        photo_urls.append(media_url)
    return {"image_urls": photo_urls}

@router.get("/destination-images-by-name")
async def get_destination_images_by_name(destination: str = Query(..., description="Destination city/place name"), count: int = Query(5, description="Number of images to return"), min_ratio: float = Query(1.5, description="Minimum ratio of width to height for landscape images")):
    # This endpoint first gets the place id from its name, then reuses the get_destination_image_by_place_id endpoint to get the images.
    if not destination or destination == "" or destination == "N/A":
        return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Destination is required"}
    cache_key = await generate_cache_key("get_destination_images_by_name", {"destination": destination.lower().strip()})
    cached_value = await retrieve_api_cache(cache_key, expires_in=31)

    # Text-search IDs-only field mask SKU — unlimited but cache-aware.
    try:
        await get_rate_limiter().consume(
            SKU["places_text_search_essentials_ids_only"],
            cache_hit=bool(cached_value),
        )
    except RateLimitExceeded as exc:
        return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Rate limit exceeded."}

    if cached_value:
        placeId = cached_value.get("placeId", "")
    else:
        if not API_KEY:
            return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Google Maps API key is not configured on the server."}
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": API_KEY,
                "X-Goog-FieldMask": "places.id"
            }
            payload = {
            "textQuery": destination,
            "maxResultCount": 1 ## This is for searching for the place which best matches the destination name
            }
            client = get_http_client()
            place_resp = await client.post(SEARCH_URL, headers=headers, json=payload, timeout=10)
            if place_resp.status_code != 200:
                return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Failed to search for the destination"}
            results = place_resp.json().get("places", [])
            if not results:
                return {"image_urls": [settings.FALLBACK_IMAGE], "error": "No results found for the destination"}
            target_place = results[0]
            placeId = target_place.get("id", "")
            if not placeId or placeId == "" or placeId == "N/A":
                return {"image_urls": [settings.FALLBACK_IMAGE], "error": "No place ID found for the destination"}
            await insert_api_cache(cache_key, {"placeId": placeId})
        except Exception:
            return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Failed to search for the destination"}
    return await get_destination_image_by_place_id(placeId, count, min_ratio)