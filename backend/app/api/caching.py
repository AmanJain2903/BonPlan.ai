# backend/app/api/caching.py

"""
Async helpers for BonPlan.ai's API cache endpoints.
"""

import hashlib
import json

from app.core.config import settings
from app.logging import get_api_logger
from app.utils.http import get_http_client

API_URL = settings.BACKEND_URL
logger = get_api_logger("api.caching")


async def generate_cache_key(api_name: str, params: dict) -> str:
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.sha256(f"{api_name}:{param_str}".encode()).hexdigest()


async def retrieve_api_cache(cache_key: str, expires_in: int = 7) -> dict | None:
    try:
        client = get_http_client()
        response = await client.get(
            f"{API_URL}/api/v1/api-cache/retrieve",
            params={"cache_key": cache_key, "expires_in": expires_in},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status_code") == 200 and "cache_value" in data:
                return data["cache_value"]
        return None
    except Exception as e:
        logger.warning("Failed to retrieve API cache", error=str(e))
        return None


async def insert_api_cache(cache_key: str, cache_value: dict) -> None:
    try:
        client = get_http_client()
        await client.post(
            f"{API_URL}/api/v1/api-cache/insert",
            json={"cache_key": cache_key, "cache_value": cache_value},
            timeout=10,
        )
    except Exception as e:
        logger.warning("Failed to insert API cache", error=str(e))