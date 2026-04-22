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
from typing import Any, Dict

from google.genai import types

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.gemini_adapter import run_chat_loop
from app.agent.langgraph_runtime.knowledge import extract_handoff_notes, render_shared_notes
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.trip_state import build_trip_state
from app.agent.schemas.structuredInput import TripInput

log = get_agent_logger("day_planner")


_MAX_PRIOR_SUMMARY_CHARS = 8000

# Per event_type: (details_field, name_field_or_None, end_location_name_field_or_None,
#                  end_coords_field_or_None, end_address_field_or_None)
_LOCATION_MAP = {
    "START":          ("start_details",          None,                    None,                None,                   None),
    "FLIGHT_TAKEOFF": ("flight_takeoff_details", "airline",               "arrival_airport",   "arrival_coordinates",  None),
    "FLIGHT_LAND":    ("flight_land_details",    "airline",               "arrival_airport",   "arrival_coordinates",  None),
    "HOTEL_CHECKIN":  ("hotel_checkin_details",  "hotel_name",            "hotel_name",        "hotel_coordinates",    "address"),
    "HOTEL_CHECKOUT": ("hotel_checkout_details", "hotel_name",            "hotel_name",        "hotel_coordinates",    "address"),
    "CAR_PICKUP":     ("car_pickup_details",     "pickup_location_name",  "pickup_location_name",  "pickup_location_coordinates",  "pickup_location_address"),
    "CAR_DROPOFF":    ("car_dropoff_details",    "dropoff_location_name", "dropoff_location_name", "dropoff_location_coordinates", "dropoff_location_address"),
    "DINING":         ("place_details",          "place_name",            "place_name",        "coordinates",          "address"),
    "ACTIVITY":       ("place_details",          "place_name",            "place_name",        "coordinates",          "address"),
    "COMMUTE":        ("commute_details",        None,                    "destinationName",   "destination_coordinates", None),
    "OTHER":          ("other_details",          "place_name",            "place_name",        "coordinates",          "address"),
    "END":            ("end_details",            None,                    None,                None,                   None),
}


def _coord_str(c) -> str:
    if not isinstance(c, dict):
        return ""
    lat = c.get("latitude")
    lng = c.get("longitude")
    if lat is None or lng is None:
        return ""
    try:
        return f"({float(lat):.4f},{float(lng):.4f})"
    except Exception:
        return ""


def _event_anchor(e: dict) -> dict:
    """
    Extract the useful anchor fields from an emitted event in a compact form:
    {name, end_name, end_coords, end_address, start_time, end_time}.
    Missing fields are returned as empty strings so callers can format simply.
    """
    etype = e.get("event_type") or ""
    details_field, name_key, end_name_key, end_coord_key, end_addr_key = _LOCATION_MAP.get(
        etype, ("", None, None, None, None)
    )
    details = e.get(details_field) or {} if details_field else {}

    name = (details.get(name_key) or "") if name_key else ""
    end_name = (details.get(end_name_key) or "") if end_name_key else ""
    end_coords = _coord_str(details.get(end_coord_key)) if end_coord_key else ""
    end_address = (details.get(end_addr_key) or "") if end_addr_key else ""
    start_time = details.get("start_time") or ""
    end_time = details.get("end_time") or ""
    return {
        "name": str(name),
        "end_name": str(end_name),
        "end_coords": end_coords,
        "end_address": str(end_address),
        "start_time": str(start_time),
        "end_time": str(end_time),
    }


def _summarize_prior_events(events: list, current_day: int) -> str:
    """
    Compact, chronological list of already-emitted events for the prompt.
    Each line now carries enough location detail for the next day to anchor
    without re-researching (critical for HOTEL_CHECKIN so Day N+1 knows where
    the traveler wakes up).
    """
    if not events:
        return "(none — this is a fresh plan)"
    lines: list[str] = []
    for e in events:
        try:
            day = e.get("day_number")
            evnum = e.get("event_number")
            etype = e.get("event_type", "")
            evname = e.get("event_name", "")
            date = e.get("date", "") or ""
            a = _event_anchor(e)
            bits = [f"- day {day} event {evnum} [{etype}] {evname}"]
            if date:
                bits.append(f"({date})")
            if a["start_time"] and a["end_time"]:
                bits.append(f"@ {a['start_time']}–{a['end_time']}")
            elif a["start_time"]:
                bits.append(f"@ {a['start_time']}")
            loc_bits = []
            if a["end_name"]:
                loc_bits.append(a["end_name"])
            if a["end_address"]:
                loc_bits.append(a["end_address"])
            if a["end_coords"]:
                loc_bits.append(a["end_coords"])
            if loc_bits:
                bits.append("→ " + " | ".join(loc_bits))
            lines.append(" ".join(bits))
        except Exception:
            continue

    # Anchor: where the traveler is right now, derived from the last event's
    # end location. Putting this at the bottom lets the model see it last
    # (recency bias) and skip the "I'll have to search for a hotel" reasoning.
    anchor_line = ""
    for e in reversed(events):
        a = _event_anchor(e)
        if a["end_coords"] or a["end_name"] or a["end_address"]:
            parts = [p for p in (a["end_name"], a["end_address"], a["end_coords"]) if p]
            anchor_line = (
                f"\nCURRENT POSITION (start of day {current_day}): "
                + " | ".join(parts)
            )
            break

    summary = "\n".join(lines) + anchor_line
    if len(summary) > _MAX_PRIOR_SUMMARY_CHARS:
        # Keep the anchor line + the tail of the log.
        body_budget = _MAX_PRIOR_SUMMARY_CHARS - len(anchor_line) - 32
        summary = (
            "… (older events truncated)\n"
            + "\n".join(lines)[-body_budget:]
            + anchor_line
        )
    return summary

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
    trip_id = state.get("trip_id") or "unknown"

    set_agent_log_context(run_id=trip_id, node="day_planner", day=current_day)
    log.info("Starting day", current_day=current_day, total_days=total_days)

    trip_payload = state.get("trip_input", {})
    trip_data = TripInput(**trip_payload)
    research_facts = state.get("research_facts", {})
    prior_events = state.get("prior_events", []) or []
    shared_notes = state.get("shared_notes", []) or []
    is_resuming = bool(state.get("is_resuming", False))
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False
        ),
        tools=[runtime.day_tool_block or runtime.planner_tool_block],
        system_instruction=AUTONOMOUS_SYSTEM_PROMPT,
        temperature=0.5,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    facts_json = json.dumps(research_facts, default=str)
    prior_summary = _summarize_prior_events(prior_events, current_day)
    trip_state_snapshot = build_trip_state(prior_events)
    trip_state_json = json.dumps(trip_state_snapshot, default=str, indent=2)
    shared_notes_block = render_shared_notes(shared_notes)
    resume_preamble = (
        "RESUME MODE — the events listed under 'Already-Emitted Events' have "
        "already been persisted. DO NOT re-emit them. DO NOT emit a START event."
        "\n\n"
        if is_resuming
        else ""
    )

    initial_message = (
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        f"Research Context:\n{facts_json}\n\n"
        f"{resume_preamble}"
        f"Already-Emitted Events (DO NOT duplicate):\n{prior_summary}\n\n"
        f"Trip State Snapshot (structured — hotels booked, flights, car rentals, "
        f"costs committed, current position). USE THIS as ground truth for what "
        f"is already arranged; do NOT re-search for items already listed here:\n"
        f"{trip_state_json}\n\n"
        f"Handoff Notes from earlier days (policies, round-trip coverage, "
        f"booking terms — these override any default assumptions; respect them "
        f"{shared_notes_block}\n\n"
        f"Phase: DAY {current_day} of {total_days}\n"
        f"Your task: plan all events for Day {current_day} ONLY. "
        f"Event numbers for Day {current_day} start from "
        f"{state.get('next_event_number', 1)} and increment by 1 per event "
        f"within this day. Emit each event immediately as you confirm the data. "
        f"When Day {current_day} is fully planned, STOP. "
        "Do NOT plan future days, and do NOT re-emit prior events."
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
        log.error("Day planner failed", current_day=current_day, error=result.error)
        return {
            "phase": "done",
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
        if new_notes:
            log.info(
                "Extracted handoff notes",
                current_day=current_day,
                note_count=len(new_notes),
            )
    except Exception as e:
        log.warning("Handoff extraction failed", current_day=current_day, error=str(e))

    log.info("Day complete", current_day=current_day)

    # Reset the per-day counter to 1 for the next day and carry same-run events
    # forward so later days see the full chronology for placement validation.
    update: dict = {
        "next_event_number": 1,
        "current_day": current_day + 1,
        "phase": "day" if current_day + 1 <= total_days else "finalize",
        "prior_events": accumulated_prior,
    }
    if new_notes:
        update["shared_notes"] = new_notes
    return update
