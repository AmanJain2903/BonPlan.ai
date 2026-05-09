"""
Deployable MCP service entrypoint.

This service exposes the BonPlan MCP server over SSE so the agent backend can
keep a single long-lived remote session open for the full process lifespan.

Important operational note:
- Run one worker per instance unless your ingress guarantees sticky routing for
  the SSE session. The transport is stateful and the follow-up POST requests
  must reach the same process that owns the open SSE stream.
"""

from app.agent.mcp_server.main import mcp
from app.core.config import settings
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse


origins = [
    settings.FRONTEND_URL,
    settings.AGENT_URL,
    settings.BACKEND_URL
]

app = mcp.http_app(
    path=settings.MCP_SSE_PATH,
    transport="sse",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.route("/health")
async def health_check(request: Request):
    """
    Explicit health check for Render to prevent spin-down.
    """
    return JSONResponse(content={"status": "ok", "service": "bonplan-mcp-sse"})
