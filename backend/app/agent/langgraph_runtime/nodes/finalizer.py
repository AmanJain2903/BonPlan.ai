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
from typing import Any, Dict, List

from google.genai import types
from sqlalchemy import select

from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary
from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.gemini_adapter import run_chat_loop
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.schemas.structuredInput import TripInput
from app.agent.langgraph_runtime.streaming import emit

log = get_agent_logger("finalizer")

_FINALIZER_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "finalizerPrompt.md"
)
with open(_FINALIZER_PROMPT_PATH, "r", encoding="utf-8") as _f:
    FINALIZER_SYSTEM_PROMPT = _f.read()


# (details_field, cost_key) pairs for every event type that contributes to the
# trip cost. Aggregated once in Python so the model never has to re-sum.
_COST_SOURCES = (
    ("flight_takeoff_details", "cost"),
    ("hotel_checkin_details", "cost"),
    ("car_pickup_details", "cost"),
    ("place_details", "cost"),
    ("other_details", "cost"),
    ("commute_details", "transit_fare"),
)


def _sum_trip_cost(events: list) -> float:
    total = 0.0
    for e in events or []:
        for field, key in _COST_SOURCES:
            details = e.get(field) or {}
            val = details.get(key)
            try:
                if val is not None:
                    total += float(val)
            except (TypeError, ValueError):
                continue
    return round(total, 2)

async def finalizer_node(state: PlannerState) -> Dict[str, Any]:
    run_id = (state.get("trip_id") + "-" + state.get("user_id")) if state.get("user_id") and state.get("trip_id") else str(uuid.uuid4())
    set_agent_log_context(run_id=run_id, node="finalizer", day=-1)
    log.info("Starting finalizer for the entire trip")

    trip_payload = state.get("trip_input", {})
    trip_data = TripInput(**trip_payload)
    research_facts = state.get("research_facts", {})
    prior_events: List[Dict] = list(state.get("prior_events") or [])

    # Load full events from DB for cost computation — prior_events in state is
    # pruned (closers and slim events) and would under-count costs.
    full_events_for_cost: List[Dict] = prior_events  # fallback
    trip_id = state.get("trip_id")
    if trip_id:
        try:
            async with Session() as db:
                itin = (
                    await db.execute(
                        select(TripItinerary).where(TripItinerary.trip_id == trip_id)
                    )
                ).scalar_one_or_none()
                if itin and itin.events:
                    full_events_for_cost = list(itin.events)
        except Exception as exc:
            log.warning(
                "finalizer: DB load failed for cost computation, using state events. This means that the trip cost is not being computed correctly.",
                trip_id=trip_id,
                error=str(exc),
            )

    # Pruned prior_events passed to LLM for context (tips generation doesn't
    # need full event details — research_facts + slim summary is sufficient).
    trip_state_json = json.dumps(prior_events, default=str)

    # Pre-compute the trip cost from full committed events so the model never
    # re-sums. Using the precomputed value keeps finalization one-shot.
    precomputed_trip_cost = _sum_trip_cost(full_events_for_cost)


    config = types.GenerateContentConfig(
        tools=[runtime.finalizer_tool_block or runtime.planner_tool_block],
        system_instruction=FINALIZER_SYSTEM_PROMPT,
        temperature=0.2,
        max_output_tokens=1024,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    initial_message = (
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        f"Research Context:\n{json.dumps(research_facts, default=str)}\n\n"
        f"Trip State Snapshot (structured):\n{trip_state_json}\n\n"
        f"PRECOMPUTED trip_cost (USD, committed): {precomputed_trip_cost}\n"
        "Phase: FINALIZE\n"
        "Emit ONE add_end_event tool call now. Rules:\n"
        f"- Set `trip_cost` to EXACTLY {precomputed_trip_cost}. Do NOT recalculate.\n"
        "- `trip_title`: a short, final title (no 'Start'/'Complete' words).\n"
        "- `trip_tips`: 3-5 concrete tips based on the research context and trip state.\n"
        "- Do NOT call any other tool. Do NOT re-read events.\n"
        "After the tool call, output ONE short final summary, then STOP."
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
