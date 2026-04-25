# backend/app/api/v1/endpoints/client_log.py

"""
Single endpoint for the frontend to ship structured log events back to the
unified backend log stream.

Designed for *selective* use — not a general firehose. The frontend should
only POST here when something happens that the backend can't observe on its
own (e.g. a Google Maps SDK call gets blocked client-side because the rate
limiter says the quota is exhausted). For everything else, ordinary HTTP
endpoints already log on the server side.

Wire format is a small JSON blob:
  {
    "event": "rate_limited",         // short kebab/snake-case label
    "sku": "dynamic_maps",           // optional: SKU we're talking about
    "level": "warning",              // info | warning | error  (default: warning)
    "message": "Map render blocked", // human readable
    "context": { ... }               // optional, free-form
  }

The endpoint always returns 200 — it is intentionally fire-and-forget on the
client side, never block the user's experience on a logging round-trip.
"""

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.logging import get_api_logger

router = APIRouter()
logger = get_api_logger("client")


class ClientLogBody(BaseModel):
    event: str = Field(..., max_length=128, description="Short event label.")
    level: Optional[str] = Field(default="warning", description="info | warning | error.")
    message: Optional[str] = Field(default=None, max_length=512)
    sku: Optional[str] = Field(default=None, max_length=128)
    context: Optional[dict[str, Any]] = None


@router.post("/log", response_model=dict)
async def submit_client_log(body: ClientLogBody, request: Request):
    # We deliberately don't trust the level — clamp to known values.
    level = (body.level or "warning").lower()
    if level not in ("info", "warning", "error"):
        level = "warning"

    extra: dict[str, Any] = {
        "event": body.event,
        "source": "frontend",
        "user_agent": request.headers.get("user-agent"),
        "client_ip": request.client.host if request.client else None,
    }
    if body.sku:
        extra["sku"] = body.sku
    if body.context:
        # Keeping it bounded so nobody can DoS the log file by shipping huge blobs.
        for k, v in list(body.context.items())[:32]:
            if k not in extra:
                extra[f"ctx_{k}"] = v

    msg = body.message or body.event
    if level == "info":
        logger.info(msg, **extra)
    elif level == "error":
        logger.error(msg, **extra)
    else:
        logger.warning(msg, **extra)

    logger.info("Client log submitted", body=body)

    return {"status_code": 200}
