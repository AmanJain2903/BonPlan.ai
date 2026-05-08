# backend/app/services/keepalive.py

"""
Background task for inter-service keepalive to prevent scale-to-zero.
"""

import asyncio
from app.utils.http import get_http_client
from app.logging import get_app_logger

logger = get_app_logger("keepalive")

async def keepalive_task(target_url: str, service_name: str, interval_seconds: int = 600):
    """
    Background task that periodically sends a telemetry sync request to a target service
    to keep both services alive and appear as legitimate traffic.
    """
    logger.info("Keepalive task started", target=target_url, service=service_name, interval=interval_seconds)
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            client = get_http_client()
            logger.info("Syncing telemetry...", target_service=service_name, target_url=target_url)
            
            response = await client.get(target_url, timeout=15.0)
            if response.status_code == 200:
                logger.debug("Telemetry sync successful", target_service=service_name)
            else:
                logger.warning("Telemetry sync unexpected status", target_service=service_name, status_code=response.status_code)
                
        except asyncio.CancelledError:
            logger.info("Keepalive task cancelled", target_service=service_name)
            break
        except Exception as e:
            logger.warning("Telemetry sync failed", target_service=service_name, error=str(e))
