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
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.schemas.structuredInput import TripInput

log = get_agent_logger("day_planner")


# ─── Open-booking pairing ────────────────────────────────────────────────────
# An "opener" event (HOTEL_CHECKIN, CAR_PICKUP, FLIGHT_TAKEOFF) must eventually
# be matched by its "closer" before the trip ends.
#
# Pairing is done via a stable (category, sub-key) bucket + FIFO within the
# bucket. Sub-keys are chosen to survive things like flight layovers (where
# flight_number differs between takeoff and land legs):
#
#   HOTEL  → hotel_name   (same on checkin and checkout)
#   CAR    → rental_company_name   (same on pickup and dropoff)
#   FLIGHT → no sub-key  — all flights share one bucket; nth takeoff pairs
#            with nth land by chronological order, so a JFK→LHR→CDG journey
#            with two legs resolves cleanly even when flight_number differs.
#
# Opener event_type → (closer event_type, details field, label field)
_OPEN_CLOSE: dict[str, tuple[str, str, str]] = {
    "HOTEL_CHECKIN":   ("HOTEL_CHECKOUT", "hotel_checkin_details",  "hotel_name"),
    "CAR_PICKUP":      ("CAR_DROPOFF",    "car_pickup_details",     "rental_company_name"),
    "FLIGHT_TAKEOFF":  ("FLIGHT_LAND",    "flight_takeoff_details", "flight_number"),
}
_CLOSE_TYPES = {close for close, _, _ in _OPEN_CLOSE.values()}


def _booking_bucket_key(event: dict) -> tuple | None:
    """Return the (category, sub-key) bucket this event belongs to, or None."""
    et = event.get("event_type")
    if et in ("HOTEL_CHECKIN", "HOTEL_CHECKOUT"):
        field = "hotel_checkin_details" if et == "HOTEL_CHECKIN" else "hotel_checkout_details"
        name = ((event.get(field) or {}).get("hotel_name") or "").strip().lower()
        return ("HOTEL", name)
    if et in ("CAR_PICKUP", "CAR_DROPOFF"):
        field = "car_pickup_details" if et == "CAR_PICKUP" else "car_dropoff_details"
        name = ((event.get(field) or {}).get("rental_company_name") or "").strip().lower()
        return ("CAR", name)
    if et in ("FLIGHT_TAKEOFF", "FLIGHT_LAND"):
        # All flights share one bucket — pairing relies on chronological order
        # within the bucket, which handles layovers where leg-level
        # flight_number or airline differs between takeoff and land.
        return ("FLIGHT", "")
    return None


def _compute_open_bookings(events: list) -> list[dict]:
    """Return descriptors for every opener event that has no matching closer yet.

    Events are grouped into (category, sub-key) buckets; within each bucket the
    nth opener (by appearance order) is paired with the nth closer. Any
    trailing openers are considered open.
    """
    buckets: dict[tuple, dict[str, list]] = {}
    for e in events:
        key = _booking_bucket_key(e)
        if key is None:
            continue
        slot = buckets.setdefault(key, {"openers": [], "closers": 0})
        et = e.get("event_type")
        if et in _OPEN_CLOSE:
            slot["openers"].append(e)
        elif et in _CLOSE_TYPES:
            slot["closers"] += 1

    open_items: list[dict] = []
    for key, slot in buckets.items():
        for idx, opener in enumerate(slot["openers"]):
            if idx < slot["closers"]:
                continue
            et = opener.get("event_type")
            close_type, open_field, label_key = _OPEN_CLOSE[et]
            details = opener.get(open_field) or {}
            open_items.append({
                "open_event_type": et,
                "must_be_closed_by": close_type,
                "opening_day_number": opener.get("day_number"),
                "opening_event_number": opener.get("event_number"),
                "label": details.get(label_key) or "",
                "bucket": list(key),
            })
    return open_items

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
    is_resuming = bool(state.get("is_resuming", False))
    close_pass = bool(state.get("close_pass", False))
    config = types.GenerateContentConfig(
        tools=[runtime.day_tool_block or runtime.planner_tool_block],
        system_instruction=AUTONOMOUS_SYSTEM_PROMPT,
        temperature=0.4,
        # Hard ceiling per turn. One event + minimal narrative fits in < 1.5k.
        # Keeps MAX_TOKENS finish_reason as an early trip-wire instead of a
        # late one that costs a full thinking pass.
        max_output_tokens=6144,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    facts_json = json.dumps(research_facts, default=str)
    trip_state_json = json.dumps(prior_events, default=str)
    resume_preamble = (
        "RESUME MODE — the events listed under 'Already-Emitted Events' have "
        "already been persisted. DO NOT re-emit them. DO NOT emit a START event."
        "\n\n"
        if is_resuming
        else ""
    )

    open_bookings = _compute_open_bookings(prior_events)
    days_remaining_after_today = max(0, total_days - current_day)
    open_bookings_block = (
        f"Open Bookings (must each receive a matching closing event before the trip ends):\n"
        f"{json.dumps(open_bookings, default=str)}\n"
        f"Days remaining AFTER today: {days_remaining_after_today}\n"
        + (
            "This is the LAST day — you MUST close every open booking today. "
            "No exceptions.\n\n"
            if days_remaining_after_today == 0 and open_bookings
            else (
                "You may close any of these today if it fits the plan, or leave "
                "them open for a later day.\n\n"
                if open_bookings
                else "No open bookings carrying over.\n\n"
            )
        )
    )

    if close_pass:
        # Dedicated close-only re-run triggered by open_booking_guard.
        task_instructions = (
            f"TASK: CLOSE-ONLY PASS for Day {current_day}. The regular day plan is already committed — "
            "you are here ONLY to emit the missing closing events listed under 'Open Bookings' above "
            "(HOTEL_CHECKOUT, CAR_DROPOFF, and/or FLIGHT_LAND as applicable) plus any COMMUTE bridges "
            "they require to respect placement rules (no teleportation between locations). "
            "Do NOT emit DINING, ACTIVITY, or OTHER events. Do NOT re-plan the day. Do NOT re-emit any "
            "event already listed under 'Already-Emitted Events'. Continue event_number from where the "
            "day left off. When every open booking has a matching closer, stop."
        )
    else:
        task_instructions = (
            f"TASK: emit every event for Day {current_day} in chronological order, one tool call at a time. "
            "Your output should **NEVER** include any thoughts or reasoning. It should only be the tool calls,"
            "one short reason to call that tol and then just emit the events."
            "**NEVER** write the ouput you get from tools as plain text. As soon as you get the output from a tool, emit the event using it."
            f"Do not plan future days. Do not re-emit prior events. "
            f"When Day {current_day} is fully emitted, stop — no summary, no recap."
        )

    initial_message = (
        f"Phase: DAY {current_day} of {total_days}\n\n"
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        f"Research Context:\n{facts_json}\n\n"
        f"Already-Emitted Events (ground truth — do NOT re-emit, do NOT re-search what these establish):\n"
        f"{trip_state_json}\n\n"
        f"{open_bookings_block}"
        f"{resume_preamble}"
        f"{task_instructions}"
    )

    result = await run_chat_loop(
        initial_message=initial_message,
        config=config,
        node_name=f"day_{current_day}",
        next_event_number=state.get("next_event_number", 1),
        current_day=current_day,
        total_days=total_days,
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

    log.info(f"Day {current_day} of {total_days} complete")

    # Reset the per-day counter to 1 for the next day and carry same-run events
    # forward so later days see the full chronology for placement validation.
    update: dict = {
        "next_event_number": 1,
        "current_day": current_day + 1,
        "prior_events": accumulated_prior,
    }
    return update
