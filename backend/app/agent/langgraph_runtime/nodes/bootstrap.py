"""
Bootstrap node — runs once at the start of every planning session.

Responsibilities:
- Parse the TripInput from state["trip_input"]
- Compute total_days from the trip dates
- Derive current_day and next_event_number from any already-emitted events
  (allows resume without re-generating completed days)
- Validate runtime readiness; emit a system error chunk if not ready

Returns state updates: total_days, current_day, next_event_number, phase.
"""
import asyncio
import uuid
from datetime import date, datetime
from typing import Any, Dict

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.streaming import emit
from app.agent.schemas.structuredInput import TripInput

log = get_agent_logger("bootstrap")


async def bootstrap_node(state: PlannerState) -> Dict[str, Any]:
    run_id = (state.get("trip_id") + "-" + state.get("user_id")) if state.get("user_id") and state.get("trip_id") else str(uuid.uuid4())
    set_agent_log_context(run_id=run_id, node="bootstrap")

    _wait_attempts = 0
    while not runtime.is_ready:
        if _wait_attempts >= 30:
            emit({"type": "error", "content": "Agent runtime never became ready."})
            log.error("Agent runtime never became ready after 30s; aborting bootstrap")
            return {"phase": "done", "cancelled": True}
        emit({
            "type": "system",
            "content": "Agent runtime initializing...",
            "error": "Agent runtime is not initialized yet. Please wait.",
        })
        log.warning("Agent runtime is not initialized yet. Please wait.")
        await asyncio.sleep(1)
        _wait_attempts += 1


    mode = state.get("mode", "autonomous")
    if mode == "editing":
        emit({
            "type": "system",
            "content": f"Mode '{mode}' not wired yet.",
            "error": "Only 'autonomous' and 'collaborative' modes are supported currently.",
        })
        log.warning(f"Mode '{mode}' not wired yet.", mode=mode)
        return {"phase": "done", "cancelled": True}

    trip_payload = state.get("trip_input", {})
    try:
        trip_data = TripInput(**trip_payload)
        log.info("Trip input validated", trip_data=trip_data)
    except Exception as exc:
        emit({"type": "error", "content": f"Invalid trip input: {exc}"})
        log.error(f"Invalid trip input: {exc}")
        return {"phase": "done", "cancelled": True}

    # total_days is derived from LOCAL wall-clock dates (what the user sees),
    # not UTC timestamps. A trip starting Jan 1 local and ending Jan 3 local is
    # a 3-day trip regardless of the UTC-offset delta.
    try:
        start_local = datetime.fromisoformat(
            trip_data.start_date.localTimeString.replace("Z", "+00:00")
        ).date()
        end_local = datetime.fromisoformat(
            trip_data.end_date.localTimeString.replace("Z", "+00:00")
        ).date()
        total_days = max(1, (end_local - start_local).days + 1)
    except Exception:
        # Fall back to the origin-date fields if localTimeString is malformed.
        try:
            start_local = date(
                trip_data.start_date.year,
                trip_data.start_date.month,
                trip_data.start_date.day,
            )
            end_local = date(
                trip_data.end_date.year,
                trip_data.end_date.month,
                trip_data.end_date.day,
            )
            total_days = max(1, (end_local - start_local).days + 1)
            log.warning("localTimeStrings malformed, used origin-date fields for total_days calculation")
        except Exception:
            total_days = max(
                1,
                (trip_data.end_date.utcTimestamp - trip_data.start_date.utcTimestamp) // 86400,
            )
            log.warning("localTimeStrings malformed, used utcTimestamp fields for total_days calculation")

    # Determine resume point from already-emitted events (passed in via initial state).
    # The caller sets state["next_event_number"] and state["current_day"] when resuming.
    current_day = state.get("current_day", 0)
    next_event_number = state.get("next_event_number", 1)
    is_resuming = bool(state.get("is_resuming", False))

    log.info(
        "Bootstrap complete",
        total_days=total_days,
        current_day=current_day,
        next_event_number=next_event_number,
        mode=mode,
        is_resuming=is_resuming
    )

    return {
        "total_days": total_days,
        "current_day": current_day,
        "next_event_number": next_event_number,
        "is_resuming": is_resuming,
        "is_complete": False
    }
