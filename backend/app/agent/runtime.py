# backend/app/agent/runtime.py

"""
Shared long-lived runtime state for the agent.

Objects here are expensive to build (GenAI client, MCP subprocess + session,
JSON-schema conversion for Gemini tool declarations) and should exist for the
entire process lifetime. They are populated by the FastAPI lifespan in
`app/ai.py` on startup and torn down on shutdown. For standalone scripts
(e.g. `test_planner.py`) use `agent_runtime_context()` below.

Per-request code should import `runtime` and use its attributes directly
instead of re-initializing these resources.

Concurrency notes:
- `genai.Client` is safe to share across async tasks.
- `ClientSession` multiplexes requests via JSON-RPC IDs, so concurrent
  `session.call_tool(...)` calls from different request handlers are safe.
- `gemini_tools` / `planner_tool_block` are immutable after startup.
"""

import os
from contextlib import asynccontextmanager
from typing import List, Optional

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings

from app.agent.schemas.structuredOutput import AddItineraryEvent
from app.agent.utils import fix_schema_for_gemini, convert_mcp_to_gemini, ADD_EVENT_TOOL


class AgentRuntime:
    genai_client: Optional[genai.Client] = None
    mcp_session: Optional[ClientSession] = None
    gemini_tools: Optional[List[types.FunctionDeclaration]] = None
    planner_tool_block: Optional[types.Tool] = None

    @property
    def is_ready(self) -> bool:
        return (
            self.genai_client is not None
            and self.mcp_session is not None
            and self.planner_tool_block is not None
        )


runtime = AgentRuntime()

@asynccontextmanager
async def agent_runtime_context():
    """
    Async context manager that starts the MCP subprocess + GenAI client,
    populates the shared `runtime` singleton, and tears everything down on
    exit. `stdio_client` and `ClientSession` use anyio task groups internally
    that must enter and exit in the same task — this helper is that single
    owner task. Used by both the FastAPI lifespan (`app/ai.py`) and by
    standalone scripts (e.g. `test_planner.py`).
    """

    try:
        runtime.genai_client = genai.Client(api_key=settings.PLANNER_AGENT_API_KEY)
    except Exception as e:
        print(f"[AGENT RUNTIME] Failed to initialize GenAI client: {e}", flush=True)
        raise

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "app.agent.mcp_server.main"],
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_response = await session.list_tools()

            gemini_tools = [convert_mcp_to_gemini(t) for t in mcp_response.tools]
            gemini_tools.append(ADD_EVENT_TOOL)

            runtime.mcp_session = session
            runtime.gemini_tools = gemini_tools
            runtime.planner_tool_block = types.Tool(function_declarations=gemini_tools)

            print(
                f"[AGENT RUNTIME] MCP session initialized with {len(mcp_response.tools)} "
                f"MCP tools (+1 add_itinerary_event) — agent is ready.",
                flush=True,
            )

            try:
                yield runtime
            finally:
                print("[AGENT RUNTIME] Tearing down MCP session and GenAI client.", flush=True)
                runtime.mcp_session = None
                runtime.gemini_tools = None
                runtime.planner_tool_block = None
                runtime.genai_client = None
