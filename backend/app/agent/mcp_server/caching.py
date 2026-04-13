import hashlib
import json
import requests
from app.core.config import settings

API_URL = settings.BACKEND_URL

def generate_cache_key(api_name: str, params: dict) -> str:
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.sha256(f"{api_name}:{param_str}".encode()).hexdigest()

def retrieve_api_cache(cache_key: str, expires_in: int = 7) -> dict:
    try:
        response = requests.get(
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
        print(f"Failed to retrieve API cache: {e}")
        return None
    
def insert_api_cache(cache_key: str, cache_value: dict) -> None:
    try:
        requests.post(
            f"{API_URL}/api/v1/api-cache/insert",
            json={"cache_key": cache_key, "cache_value": cache_value},
            timeout=10,
        )
    except Exception as e:
        print(f"Failed to insert API cache: {e}")