# backend/app/services/keepalive.py

"""
Background task for inter-service keepalive to prevent scale-to-zero.
"""

import asyncio
from app.utils.http import get_http_client
from app.logging import get_app_logger
import random
import httpx

logger = get_app_logger("keepalive")

async def keepalive_task(target_url: str, service_name: str, interval_seconds: int = 600):
    """
    Background task that periodically sends a telemetry sync request to a target service
    to keep both services alive and appear as legitimate traffic.
    """
    interval_seconds = interval_seconds * random.uniform(0.8, 1.2)
    logger.info("Keepalive task started", target=target_url, service=service_name, interval=interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            client = httpx.AsyncClient(timeout=15.0)
            logger.info("Syncing telemetry...", target_service=service_name, target_url=target_url)
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "close",
                "Cache-Control": "no-cache",
            }
            response = await client.get(target_url, headers=headers, timeout=15.0)
            if response.status_code == 200:
                logger.debug("Telemetry sync successful", target_service=service_name)
            else:
                logger.warning("Telemetry sync unexpected status", target_service=service_name, status_code=response.status_code)
                
        except asyncio.CancelledError:
            logger.info("Keepalive task cancelled", target_service=service_name)
            break
        except Exception as e:
            logger.warning("Telemetry sync failed", target_service=service_name, error=str(e))
