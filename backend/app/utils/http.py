# backend/app/utils/http.py

"""
Process-wide shared httpx.AsyncClient.

One client per process avoids TCP+TLS handshake overhead on every outbound
call. For FastAPI processes (app.py, ai.py), the lifespan closes it on
shutdown; for the MCP subprocess, it's cleaned up on process exit.
"""

from typing import Optional

import httpx

from app.core.config import settings

_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    """Returns the process-wide shared httpx.AsyncClient (lazy-initialized)."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": settings.HTTP_USER_AGENT},
        )
    return _client


async def close_http_client() -> None:
    """Close the shared client. Safe to call multiple times."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None
