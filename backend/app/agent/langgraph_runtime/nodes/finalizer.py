"""
Finalizer node.

Runs a short chat loop that:
  1. Emits the END event (day_number=-1) with a cost summary
  2. Outputs a final summary text (the SSE endpoint uses this as success signal)

If the model fails to emit END, the node emits a synthetic END so the frontend
always receives a valid terminal state.
"""
import json
import os
import uuid
from typing import Any, Dict

from google.genai import types

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.gemini_adapter import run_chat_loop
from app.agent.langgraph_runtime.knowledge import render_shared_notes
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.schemas.structuredInput import TripInput
from app.agent.langgraph_runtime.streaming import emit

log = get_agent_logger("finalizer")

_FINALIZER_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "finalizerPrompt.md"
)
with open(_FINALIZER_PROMPT_PATH, "r", encoding="utf-8") as _f:
    FINALIZER_SYSTEM_PROMPT = _f.read()

async def finalizer_node(state: PlannerState) -> Dict[str, Any]:
    run_id = (state.get("trip_id") + "-" + state.get("owner_id")) if state.get("owner_id") and state.get("trip_id") else str(uuid.uuid4())
    set_agent_log_context(run_id=run_id, node="finalizer", day=-1)
    log.info("Starting finalizer for the entire trip")

    trip_payload = state.get("trip_input", {})
    trip_data = TripInput(**trip_payload)
    research_facts = state.get("research_facts", {})
    prior_events = state.get("prior_events", []) or []
    total_days = state.get("total_days", 1)

    trip_state_json = json.dumps(prior_events, default=str)

    shared_notes_block = render_shared_notes(state.get("shared_notes", []) or [])

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
        ),
        tools=[runtime.finalizer_tool_block or runtime.planner_tool_block],
        system_instruction=FINALIZER_SYSTEM_PROMPT,
        temperature=0.3,
        max_output_tokens=2048,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    initial_message = (
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        f"Research Context:\n{json.dumps(research_facts, default=str)}\n\n"
        f"Trip State Snapshot (structured):\n{trip_state_json}\n\n"
        f"Handoff Notes accumulated across days (round-trip coverage, "
        f"checkout policies, fuel rules, etc.):\n{shared_notes_block}\n\n"
        "Phase: FINALIZE\n"
        "All trip days have been planned. Your task:\n"
        "1. Emit the END event (event_type='END', day_number=-1) with a complete "
        "cost breakdown tips and everything required in end_details — base trip_cost on the committed per-event "
        "costs above; do NOT invent numbers.\n"
        "2. After emitting END, output a brief final summary in plain text.\n"
        "STOP after the summary.\n"
        "Begin now."
    )

    result = await run_chat_loop(
        initial_message=initial_message,
        config=config,
        node_name="finalizer",
        next_event_number=state.get("next_event_number", 1),
        mode=state.get("mode", "autonomous"),
        prior_events=state.get("prior_events", []) or [],
        stop_after_start=False,
    )

    if not result.is_complete:
        log.error("Finalizer did not emit END for the entire trip", error=result.error)
        emit({
            "type": "error",
            "content": "Finalizer did not emit END event. The itinerary may be incomplete.",
        })

    log.info("Finalizer complete", is_complete=result.is_complete)
    return {
        "is_complete": result.is_complete,
        "next_event_number": result.next_event_number,
        "phase": "done",
    }
