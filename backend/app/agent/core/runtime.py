# backend/app/agent/runtime.py

"""
Shared long-lived runtime state for the agent.

Objects here are expensive to build (LLM client config, remote MCP session,
JSON-schema conversion for tool declarations) and should exist for the entire
process lifetime. They are populated by the FastAPI lifespan in `app/ai.py` on
startup and torn down on shutdown. For standalone scripts (e.g.
`test_planner.py`) use `agent_runtime_context()` below.

Per-request code should import `runtime` and use its attributes directly
instead of re-initializing these resources.

Concurrency notes:
- LiteLLM calls are stateless and safe to issue across async tasks.
- `ClientSession` multiplexes requests via JSON-RPC IDs, so concurrent
  `session.call_tool(...)` calls from different request handlers are safe.
- `llm_tools` / `planner_tool_block` are immutable after startup.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.core.config import settings
from app.logging import get_agent_logger
from app.agent.llm import litellm_types as types
from app.agent.llm.litellm_client import LiteLLMClient

from app.agent.schemas.structuredOutput import AddItineraryEvent
from app.agent.helpers.utils import (
    convert_mcp_to_llm_tool,
    ADD_EVENT_TOOL,
    ASK_USER_QUESTION_TOOL,
    PER_TYPE_EVENT_TOOLS,
    build_phase_tool_block,
    RESEARCH_EVENT_TOOL_NAMES,
    DAY_EVENT_TOOL_NAMES,
    FINALIZER_EVENT_TOOL_NAMES,
)

log = get_agent_logger("runtime")

_MCP_HEALTH_INTERVAL_SECONDS = 30


# ─────────────────────────────────────────────────────────────────────────────
# Per-phase MCP tool allow-lists.
#
# Shrinking the tool manifest per node keeps the input-token budget flat and
# removes "distracting" tools the model could call for no reason. Any MCP tool
# whose name is absent from the phase's list is not exposed to the LLM during
# that phase.
#
# If a tool name in these lists is missing on the MCP server (e.g. one was
# removed), it is simply skipped — no hard error.
# ─────────────────────────────────────────────────────────────────────────────
_RESEARCH_MCP_TOOLS: set[str] = {
    # Timezone / time math
    "get_timezone",
    "convert_target_local_time_to_utc",
    # Weather & air quality
    "get_current_weather",
    "get_daily_forecast",
    "get_hourly_forecast",
    "get_current_air_quality",
    "get_air_quality_forecast",
    # Geocoding
    "get_optimal_route",
    # Web
    "search_web",
    "get_content_from_url",
    # Currency
    "get_supported_currencies",
    "convert_currency_to_USD",
}

_DAY_MCP_TOOLS: set[str] = {
    # Timezone / time math
    "get_current_timestamp",
    "get_timezone",
    "convert_utc_string_to_timestamp",
    "convert_timestamp_to_utc_string",
    "convert_target_local_time_to_utc",
    # Geocoding
    "get_coordinates",
    "get_address",
    "get_optimal_route",
    # Routing
    "get_route",
    "get_route_matrix",
    # Places
    "search_places",
    "search_places_nearby",
    "get_place_info",
    # Web
    "search_web",
    "get_content_from_url",
    # Flights
    "get_country_code",
    "get_airports_and_codes",
    "search_flights",
    "search_multi_city_flights",
    "get_next_flights",
    "get_flight_booking_details",
    "get_flight_booking_url",
    # Rental cars
    "search_rental_cars",
    # Hotels
    "search_hotels",
    "get_hotel_booking_url",
    # Currency
    "get_supported_currencies",
    "convert_currency_to_USD",
}

_FINALIZER_MCP_TOOLS: set[str] = {
    # No tools needed for the finalizer but currency tools are needed for the finalizer to convert the currency to USD for the final summary if not in USD already.(RARE)
    # Currency
    "get_supported_currencies",
    "convert_currency_to_USD",
}


def _filter_mcp_decls(
    mcp_decls: List[types.FunctionDeclaration],
    allow: set[str],
) -> List[types.FunctionDeclaration]:
    return [d for d in mcp_decls if d.name in allow]


class AgentRuntime:
    model_client: Optional[LiteLLMClient] = None
    pruning_client: Optional[LiteLLMClient] = None  # small/fast model for history summarization and handoff-note extraction
    mcp_session: Optional[ClientSession] = None
    llm_tools: Optional[List[types.FunctionDeclaration]] = None
    planner_tool_block: Optional[types.Tool] = None
    research_tool_block: Optional[types.Tool] = None
    day_tool_block: Optional[types.Tool] = None
    day_tool_block_collaborative: Optional[types.Tool] = None
    finalizer_tool_block: Optional[types.Tool] = None
    editor_tool_block: Optional[types.Tool] = None
    planner_graph: Optional[Any] = None
    editor_graph: Optional[Any] = None
    checkpointer: Optional[Any] = None
    mcp_healthy: bool = True

    @property
    def is_ready(self) -> bool:
        return (
            self.model_client is not None
            and self.mcp_session is not None
            and self.planner_tool_block is not None
        )


runtime = AgentRuntime()


async def _mcp_health_ping(session: ClientSession) -> None:
    """Background task: periodically pings MCP. Flips `runtime.mcp_healthy`."""
    while True:
        try:
            await asyncio.sleep(_MCP_HEALTH_INTERVAL_SECONDS)
            await asyncio.wait_for(session.list_tools(), timeout=10)
            if not runtime.mcp_healthy:
                log.info("MCP session recovered")
            runtime.mcp_healthy = True
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if runtime.mcp_healthy:
                log.error("MCP session unhealthy", error=str(e))
            runtime.mcp_healthy = False


@asynccontextmanager
async def agent_runtime_context():
    """
    Async context manager that opens the long-lived remote MCP SSE session +
    LiteLLM client, populates the shared `runtime` singleton, and tears
    everything down on exit. `sse_client` and `ClientSession` use anyio task
    groups internally that must enter and exit in the same task — this helper
    is that single owner task. Used by both the FastAPI lifespan (`app/ai.py`)
    and by standalone scripts (e.g. `test_planner.py`).
    """

    try:
        runtime.model_client = LiteLLMClient()
        log.info("LiteLLM client initialized")
    except Exception as e:
        log.error("Failed to initialize LiteLLM client", error=str(e))
        raise

    try:
        runtime.pruning_client = runtime.model_client
        log.info("Pruning client initialized")
    except Exception as e:
        # Non-fatal: summarization pruning falls back to drop-oldest behavior.
        runtime.pruning_client = None
        log.info("Pruning client unavailable, will fall back to drop-oldest behavior and handoff-note extraction will not be available", error=str(e))

    async with sse_client(
        settings.MCP_URL + settings.MCP_SSE_PATH,
        timeout=10,
        sse_read_timeout=max(_MCP_HEALTH_INTERVAL_SECONDS * 3, 90),
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_response = await session.list_tools()

            mcp_decls = [convert_mcp_to_llm_tool(t) for t in mcp_response.tools]

            # Legacy full block (keeps monolithic add_itinerary_event for any
            # caller that hasn't migrated yet — e.g. tests).
            llm_tools = list(mcp_decls) + [ADD_EVENT_TOOL]

            runtime.mcp_session = session
            runtime.llm_tools = llm_tools
            runtime.planner_tool_block = types.Tool(function_declarations=llm_tools)
            runtime.mcp_healthy = True

            research_mcp_decls = _filter_mcp_decls(mcp_decls, _RESEARCH_MCP_TOOLS)
            day_mcp_decls = _filter_mcp_decls(mcp_decls, _DAY_MCP_TOOLS)
            finalizer_mcp_decls = _filter_mcp_decls(mcp_decls, _FINALIZER_MCP_TOOLS)
            editor_mcp_decls = list(mcp_decls)

            runtime.research_tool_block = build_phase_tool_block(
                research_mcp_decls, RESEARCH_EVENT_TOOL_NAMES
            )
            runtime.day_tool_block = build_phase_tool_block(
                day_mcp_decls, DAY_EVENT_TOOL_NAMES
            )
            runtime.day_tool_block_collaborative = build_phase_tool_block(
                day_mcp_decls, DAY_EVENT_TOOL_NAMES, ask_user_question_tool=ASK_USER_QUESTION_TOOL
            )
            runtime.finalizer_tool_block = build_phase_tool_block(
                finalizer_mcp_decls, FINALIZER_EVENT_TOOL_NAMES
            )
            runtime.editor_tool_block = types.Tool(function_declarations=editor_mcp_decls)

            health_task = asyncio.create_task(_mcp_health_ping(session))

            # In-memory checkpointer is sufficient today — resume is rebuilt
            # from the DB on every call via current_trip_itinerary, so durable
            # LangGraph checkpoints would only duplicate state. When
            # collaborative / editing modes land (which need mid-graph
            # interrupts across HTTP requests) we can re-introduce
            # AsyncPostgresSaver here.
            from langgraph.checkpoint.memory import MemorySaver
            checkpointer = MemorySaver()
            runtime.checkpointer = checkpointer

            from app.agent.langgraph_runtime.graph import build_planner_graph, build_editor_graph
            # Build the compiled graph once, with the resolved checkpointer.
            runtime.planner_graph = build_planner_graph(checkpointer=checkpointer)
            runtime.editor_graph = build_editor_graph(checkpointer=checkpointer)

            log.info(
                f"Remote MCP session initialized from {settings.MCP_URL} and path {settings.MCP_SSE_PATH} with "
                f"{len(mcp_response.tools)} MCP tools + per-type event tools "
                f"(research/day/finalizer blocks) — agent is ready.",
                flush=True,
            )

            try:
                yield runtime
            finally:
                log.info("Tearing down remote MCP session and LiteLLM client.")
                health_task.cancel()
                try:
                    await health_task
                except BaseException:
                    pass
                runtime.mcp_session = None
                runtime.llm_tools = None
                runtime.planner_tool_block = None
                runtime.research_tool_block = None
                runtime.day_tool_block = None
                runtime.day_tool_block_collaborative = None
                runtime.finalizer_tool_block = None
                runtime.editor_tool_block = None
                runtime.planner_graph = None
                runtime.editor_graph = None
                runtime.checkpointer = None
                runtime.model_client = None
                runtime.pruning_client = None
                runtime.mcp_healthy = False
