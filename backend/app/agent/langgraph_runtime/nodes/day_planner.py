"""
Day planner node.

Runs for each trip day (current_day 1..total_days).  Each invocation starts
with a completely fresh chat history — no cross-day context accumulation.

The day-specific prompt is injected as the initial user message along with the
compact research_facts summary.  The chat loop runs until the model returns
STOP, which signals that all events for the day have been emitted.

After this node finishes, current_day is incremented so the graph can decide
whether to loop back for the next day or route to finalizer.
"""
import json
import os
import uuid
from typing import Any, Dict

from google.genai import types

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.gemini_adapter import run_chat_loop
from app.agent.langgraph_runtime.knowledge import extract_handoff_notes, render_shared_notes
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.schemas.structuredInput import TripInput

log = get_agent_logger("day_planner")

_AUTONOMOUS_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "autonomousPlannerPrompt.md"
)
with open(_AUTONOMOUS_PROMPT_PATH, "r", encoding="utf-8") as _f:
    AUTONOMOUS_SYSTEM_PROMPT = _f.read()

# _COLLABORATIVE_PROMPT_PATH = os.path.join(
#     os.path.dirname(__file__), "..", "..", "prompts", "collaborativePlannerPrompt.md"
# )
# with open(_COLLABORATIVE_PROMPT_PATH, "r", encoding="utf-8") as _f:
#     COLLABORATIVE_SYSTEM_PROMPT = _f.read()

# _EDITING_PROMPT_PATH = os.path.join(
#     os.path.dirname(__file__), "..", "..", "prompts", "editingPlannerPrompt.md"
# )
# with open(_EDITING_PROMPT_PATH, "r", encoding="utf-8") as _f:
#     EDITING_SYSTEM_PROMPT = _f.read()


async def day_planner_node(state: PlannerState) -> Dict[str, Any]:
    current_day = state.get("current_day", 1)
    total_days = state.get("total_days", 1)
    run_id = (state.get("trip_id") + "-" + state.get("owner_id")) if state.get("owner_id") and state.get("trip_id") else str(uuid.uuid4())

    set_agent_log_context(run_id=run_id, node="day_planner", day=current_day)
    log.info(f"Starting day {current_day} of {total_days}")

    trip_payload = state.get("trip_input", {})
    trip_data = TripInput(**trip_payload)
    research_facts = state.get("research_facts", {})
    prior_events = state.get("prior_events", []) or []
    shared_notes = state.get("shared_notes", []) or []
    is_resuming = bool(state.get("is_resuming", False))
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False,
        ),
        tools=[runtime.day_tool_block or runtime.planner_tool_block],
        system_instruction=AUTONOMOUS_SYSTEM_PROMPT,
        temperature=0.4,
        # Hard ceiling per turn. One event + minimal narrative fits in < 1.5k.
        # Keeps MAX_TOKENS finish_reason as an early trip-wire instead of a
        # late one that costs a full thinking pass.
        max_output_tokens=2048,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    facts_json = json.dumps(research_facts, default=str)
    trip_state_json = json.dumps(prior_events, default=str)
    shared_notes_block = render_shared_notes(shared_notes)
    resume_preamble = (
        "RESUME MODE — the events listed under 'Already-Emitted Events' have "
        "already been persisted. DO NOT re-emit them. DO NOT emit a START event."
        "\n\n"
        if is_resuming
        else ""
    )

    initial_message = (
        f"Phase: DAY {current_day} of {total_days}\n\n"
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        f"Research Context:\n{facts_json}\n\n"
        f"Already-Emitted Events (ground truth — do NOT re-emit, do NOT re-search what these establish):\n"
        f"{trip_state_json}\n\n"
        f"Handoff Notes (policies + bookings carried from prior days — trust these):\n"
        f"{shared_notes_block}\n\n"
        f"{resume_preamble}"
        f"TASK: emit every event for Day {current_day} in chronological order, one tool call at a time. "
        f"Close any open bookings from prior days whose end falls today (hotel checkout, flight landing, car return). "
        f"Do not plan future days. Do not re-emit prior events. "
        f"When Day {current_day} is fully emitted, stop — no summary, no recap."
    )

    result = await run_chat_loop(
        initial_message=initial_message,
        config=config,
        node_name=f"day_{current_day}",
        next_event_number=state.get("next_event_number", 1),
        mode=state.get("mode", "autonomous"),
        is_resuming=is_resuming,
        prior_events=prior_events,
        stop_after_start=False,
        require_end=False,
    )

    new_events = list(result.emitted_events or [])
    accumulated_prior = list(prior_events) + new_events

    if not result.success and not result.is_complete:
        log.error(f"Day planner failed for day {current_day}", error=result.error)
        return {
            "cancelled": True,
            "next_event_number": 1,
            "current_day": current_day + 1,
            "prior_events": accumulated_prior,
        }

    # Extract durable handoff notes from this day's search-tool responses so
    # future days inherit policies / round-trip coverage / booking terms.
    new_notes: list = []
    try:
        new_notes = await extract_handoff_notes(
            day_number=current_day,
            session_events=new_events,
            tool_findings=list(result.tool_findings or []),
        )
    except Exception as e:
        log.warning(f"Handoff extraction failed for day {current_day}", error=str(e))

    log.info(f"Day {current_day} of {total_days} complete")

    # Reset the per-day counter to 1 for the next day and carry same-run events
    # forward so later days see the full chronology for placement validation.
    update: dict = {
        "next_event_number": 1,
        "current_day": current_day + 1,
        "prior_events": accumulated_prior,
    }
    if new_notes:
        update["shared_notes"] = new_notes
    return update
