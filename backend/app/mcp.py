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


app = mcp.http_app(
    path=settings.MCP_SSE_PATH,
    transport="sse",
)
