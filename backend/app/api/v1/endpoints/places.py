# backend/app/api/v1/endpoints/places.py

"""

This file contains the places endpoints for the v1 version of the API.

Includes a server-side image proxy that downloads Google Places photos once,
caches them in PostgreSQL, and serves them to the frontend. This prevents
repeated Google API billing on every browser render.

Local dev: raw bytes stored in Postgres, served via /place-photo proxy endpoint.
Prod: bytes uploaded to Cloudflare R2, R2 URL stored in Postgres, frontend hits R2 directly.
"""

from datetime import datetime, timedelta, timezone

import asyncio
import boto3

from fastapi import APIRouter, Query, Response
from fastapi.responses import RedirectResponse
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

from app.logging import get_api_logger

logger = get_api_logger("api.places")

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

R2_PHOTO_BASE_URL = settings.CLOUDFLARE_R2_PHOTO_CACHE_BASE_URL

_r2_client = None
if not settings.LOCAL_DEVELOPMENT:
    _r2_client = boto3.client(
        service_name="s3",
        endpoint_url=settings.CLOUDFLARE_R2_ENDPOINT_URL,
        aws_access_key_id=settings.CLOUDFLARE_R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.CLOUDFLARE_R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


async def _upload_to_r2(resource_name: str, image_bytes: bytes, content_type: str) -> str:
    file_key = f"photo_cache/{resource_name}.jpg"
    await asyncio.to_thread(
        _r2_client.put_object,
        Bucket=settings.CLOUDFLARE_R2__PHOTO_CACHE_BUCKET_NAME,
        Key=file_key,
        Body=image_bytes,
        ContentType=content_type,
    )
    return f"{R2_PHOTO_BASE_URL}/{file_key}"


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
    except Exception as e:
        logger.warning("Failed to check image brightness. Returning True", error=str(e))
        return True

async def _build_proxy_url(resource_name: str, db: Session) -> str:
    """Build a URL that points to our own proxy endpoint (local) or R2 (prod)."""
    result = (await db.execute(
        select(PlacePhotoCache).where(PlacePhotoCache.resource_name == resource_name)
    )).scalar_one_or_none()

    if result:
        if result.created_at and result.created_at < datetime.now(timezone.utc) - timedelta(days=PHOTO_CACHE_TTL_DAYS):
            # Expired — delete and re-fetch
            await db.delete(result)
            await db.commit()
            result = None

    imageBytes = None

    if result:
        if not settings.LOCAL_DEVELOPMENT:
            # Prod: R2 URL already stored, brightness validated on write
            return result.r2_url
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
        except Exception as e:
            logger.warning("Failed to fetch image from Google", error=str(e))
            return None
        if google_resp.status_code != 200:
            logger.warning("Google returned non-200 status code", resource_name=resource_name, status_code=google_resp.status_code)
            return None
        imageBytes = google_resp.content
        content_type = google_resp.headers.get("content-type", "image/jpeg")

        if not await _is_bright_enough(imageBytes):
            return None

        try:
            if settings.LOCAL_DEVELOPMENT:
                db.add(PlacePhotoCache(resource_name=resource_name, image_data=imageBytes, content_type=content_type))
                await db.commit()
            else:
                r2_url = await _upload_to_r2(resource_name, imageBytes, content_type)
                db.add(PlacePhotoCache(resource_name=resource_name, r2_url=r2_url, content_type=content_type))
                await db.commit()
                return r2_url
        except Exception as e:
            logger.warning("Failed to cache image.", resource_name=resource_name, error=str(e))
            await db.rollback()
            if not settings.LOCAL_DEVELOPMENT:
                return None

    # Local dev path: serve via proxy endpoint
    if not imageBytes:
        return None
    if not await _is_bright_enough(imageBytes):
        return None
    return f"{BACKEND_URL}/api/v1/places/place-photo/{resource_name}"


@router.get("/place-photo/{resource_name:path}")
async def get_place_photo(resource_name: str):
    """
    Image proxy endpoint. Local dev: serves cached photo binary from Postgres.
    Prod: redirects to R2 URL (this endpoint should not be called in prod).
    """
    async with Session() as db:
        result = (await db.execute(
            select(PlacePhotoCache).where(PlacePhotoCache.resource_name == resource_name)
        )).scalar_one_or_none()

        if result:
            if not settings.LOCAL_DEVELOPMENT and result.r2_url:
                return RedirectResponse(url=result.r2_url)
            if result.image_data:
                return Response(
                    content=result.image_data,
                    media_type=result.content_type,
                    headers={
                        "Cache-Control": f"public, max-age={PHOTO_CACHE_TTL_DAYS * 86400}, immutable",
                        "X-Photo-Cache": "HIT",
                        "Access-Control-Allow-Origin": "*",
                    },
                )

        logger.warning(f"Unable to fetch image for {resource_name}. Returning Fallback Image")
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
    if not photo_urls:
        return {"image_urls": [settings.FALLBACK_IMAGE]}
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
        except Exception as e:
            logger.error("Failed to search for the destination name", destination=destination, error=str(e))
            return {"image_urls": [settings.FALLBACK_IMAGE], "error": "Failed to search for the destination"}
    return await get_destination_image_by_place_id(placeId, count, min_ratio)
