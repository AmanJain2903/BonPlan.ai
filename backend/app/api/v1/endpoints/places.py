# backend/app/api/v1/endpoints/places.py

"""
This file contains the places endpoints for the v1 version of the API.
"""

from fastapi import APIRouter, HTTPException, Query
import requests
import random
from typing import Dict, List
from app.core.config import settings

router = APIRouter()

# In-memory caches to secure against Google Rate Limits and save network roundtrips
# Store 1: Maps a City/Destination string to an array of Google Photo References
photo_cache: Dict[str, List[str]] = {}

# Store 2: Maps a Google Photo Reference directly to the final resolved image URL
resolved_url_cache: Dict[str, str] = {}

# Default generic beautiful image fallback to prevent frontend UI breakage
FALLBACK_IMAGE = settings.FALLBACK_IMAGE

maxWidth = 1080

@router.get("/destination-image")
def get_destination_image(destination: str = Query(..., description="Destination city/place name")):
    api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED
    if not api_key:
        return {"image_url": FALLBACK_IMAGE}

    lower_dest = destination.lower().strip()
    
    # 1. Ensure we have an array of Google Photo References for this Destination
    if lower_dest not in photo_cache or not photo_cache[lower_dest]:
        try:
            # text search for Place ID
            find_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            find_params = {
                "input": destination,
                "inputtype": "textquery",
                "fields": "place_id",
                "key": api_key
            }
            resp = requests.get(find_url, params=find_params, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "OK" and data.get("candidates"):
                    place_id = data["candidates"][0]["place_id"]
                    
                    # Fetch all photo references (up to 10) for maximum random variance
                    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                    details_params = {
                        "place_id": place_id,
                        "fields": "photos",
                        "key": api_key
                    }
                    resp2 = requests.get(details_url, params=details_params, timeout=5)
                    data2 = resp2.json()
                    
                    photos = data2.get("result", {}).get("photos", [])
                    photo_cache[lower_dest] = [p["photo_reference"] for p in photos]
        except Exception:
            pass # Silent catch - empty cache triggers Fallback below naturally
            
    available_photos = photo_cache.get(lower_dest, [])
    if not available_photos:
        # Highly robust fallback if city lacks pictures
        return {"image_url": FALLBACK_IMAGE}
        
    # 2. Pick random photo references and attempt to resolve to final URLs
    # We shuffle the list to get dynamic pictures on frontend reloads
    random.shuffle(available_photos)
    
    # Iterate through up to 3 different photos until one succeeds to prevent 500s 
    try_count = min(3, len(available_photos))
    for i in range(try_count):
        photo_ref = str(available_photos[i])
        
        # Fast path O(1) cache hit! Prevents Google Request overhead
        if photo_ref in resolved_url_cache:
            return {"image_url": resolved_url_cache[photo_ref]}
            
        photo_url = "https://maps.googleapis.com/maps/api/place/photo"
        photo_params = {
            "maxwidth": maxWidth,
            "photo_reference": photo_ref,
            "key": str(api_key)
        }
        
        try:
            # Follow redirect logic off, grab the direct source URL from Location header
            photo_resp = requests.get(photo_url, params=photo_params, allow_redirects=False, timeout=4)
            if photo_resp.status_code in (301, 302, 303, 307, 308):
                final_url = photo_resp.headers.get("Location")
                if final_url is not None:
                    final_url_str = str(final_url)
                    # Cache the raw image URL permanently so we never hit Google API for this ref again!
                    resolved_url_cache[photo_ref] = final_url_str
                    return {"image_url": final_url_str}
        except Exception:
            continue # Try the next photo in the shuffled list
            
    # Exhausted 3 attempts without a single resolution, drop gracefully
    return {"image_url": FALLBACK_IMAGE}


@router.get("/destination-images")
def get_destination_images(
    destination: str = Query(..., description="Destination city/place name"), 
    count: int = Query(10, description="Number of images to return"), 
    min_ratio: float = Query(1.4, description="Minimum ratio of width to height for landscape images")
):
    api_key = settings.GOOGLE_MAPS_API_KEY_UNRESTRICTED
    if not api_key:
        return {"image_urls": [FALLBACK_IMAGE]}

    lower_dest = destination.lower().strip()
    
    # 1. Ensure we have an array of Google Photo References for this Destination
    if lower_dest not in photo_cache or not photo_cache[lower_dest]:
        try:
            # text search for Place ID
            find_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            find_params = {
                "input": destination,
                "inputtype": "textquery",
                "fields": "place_id",
                "key": api_key
            }
            resp = requests.get(find_url, params=find_params, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "OK" and data.get("candidates"):
                    place_id = data["candidates"][0]["place_id"]
                    
                    # Fetch all photo references (up to 10) for maximum random variance
                    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
                    details_params = {
                        "place_id": place_id,
                        "fields": "photos",
                        "key": api_key
                    }
                    resp2 = requests.get(details_url, params=details_params, timeout=5)
                    data2 = resp2.json()
                    
                    photos = data2.get("result", {}).get("photos", [])

                    landscape_refs = []
                    for p in photos:
                        width = p.get("width", 1)
                        height = p.get("height", 1)
                        # A ratio of 1.2 or higher guarantees a wide landscape format
                        if (width / height) >= min_ratio:
                            landscape_refs.append(p["photo_reference"])
                    
                    photo_cache[lower_dest] = landscape_refs
        except Exception:
            pass # Silent catch - empty cache triggers Fallback below naturally
            
    available_photos = photo_cache.get(lower_dest, [])
    if not available_photos:
        # Highly robust fallback if city lacks pictures
        return {"image_urls": [FALLBACK_IMAGE]}
        
    # 2. Pick random photo references and attempt to resolve to final URLs
    # We shuffle the list to get dynamic pictures on frontend reloads
    random.shuffle(available_photos)
    
    target_count = min(count, len(available_photos))
    final_urls = []
    for photo_ref in available_photos:
        if len(final_urls) >= target_count:
            break
        # Fast path O(1) cache hit! Prevents Google Request overhead
        if photo_ref in resolved_url_cache:
            final_urls.append(resolved_url_cache[photo_ref])
            continue
            
        photo_url = "https://maps.googleapis.com/maps/api/place/photo"
        photo_params = {
            "maxwidth": maxWidth,
            "photo_reference": photo_ref,
            "key": str(api_key)
        }
        
        try:
            # Follow redirect logic off, grab the direct source URL from Location header
            photo_resp = requests.get(photo_url, params=photo_params, allow_redirects=False, timeout=4)
            if photo_resp.status_code in (301, 302, 303, 307, 308):
                final_url = photo_resp.headers.get("Location")
                if final_url is not None:
                    final_url_str = str(final_url)
                    # Cache the raw image URL permanently so we never hit Google API for this ref again!
                    resolved_url_cache[photo_ref] = final_url_str
                    final_urls.append(final_url_str)
        except Exception:
            continue # Try the next photo in the shuffled list
    
    if not final_urls:
        return {"image_urls": [FALLBACK_IMAGE]}
    return {"image_urls": final_urls}