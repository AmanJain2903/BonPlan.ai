"""
Open-booking guard node.

Runs after the day-planner loop finishes (current_day > total_days) and before
the finalizer. Checks whether any opener event (HOTEL_CHECKIN, CAR_PICKUP,
FLIGHT_TAKEOFF) lacks its matching closer in prior_events.

  • If no open bookings → pass through to the finalizer.
  • If open bookings exist and no close pass has been attempted yet → route
    back to the day planner with close_pass=True on day=total_days for a
    dedicated close-only pass (continuing event_number from where the last
    day left off).
  • If open bookings still exist after one close pass → log and give up,
    routing to finalizer anyway so the trip still terminates cleanly.
"""
import uuid
from typing import Any, Dict, List

from sqlalchemy import select

from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary
from app.logging import get_agent_logger, set_agent_log_context
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.validator import _compute_open_bookings

log = get_agent_logger("open_booking_guard")


def _next_event_number_for_day(prior_events: list, day: int) -> int:
    nums = [
        e.get("event_number") or 0
        for e in prior_events
        if e.get("day_number") == day and isinstance(e.get("event_number"), int)
    ]
    return (max(nums) + 1) if nums else 1


async def open_booking_guard_node(state: PlannerState) -> Dict[str, Any]:
    run_id = (
        (state.get("trip_id") + "-" + state.get("user_id"))
        if state.get("user_id") and state.get("trip_id")
        else str(uuid.uuid4())
    )
    set_agent_log_context(run_id=run_id, node="open_booking_guard", day=-1)

    prior_events: List[Dict] = list(state.get("prior_events") or [])
    total_days = state.get("total_days", 1)

    # Load full events from DB — prior_events in state may be pruned (closers
    # dropped), which would make _compute_open_bookings inaccurate.
    full_events_for_check = prior_events  # fallback if DB unavailable
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
                    full_events_for_check = list(itin.events)
        except Exception as exc:
            log.warning(
                "open_booking_guard: DB load failed, falling back to state events. This means that the open bookings are not being computed correctly.",
                trip_id=trip_id,
                error=str(exc),
            )

    open_items = _compute_open_bookings(full_events_for_check)

    if not open_items:
        return {"close_pass": False, "phase": "finalize"}

    if state.get("close_pass_attempted"):
        log.error(
            "Open bookings still present after close pass — proceeding to finalizer anyway",
            count=len(open_items),
            open=open_items,
        )
        return {"close_pass": False, "phase": "finalize"}

    log.info(
        "Open bookings detected — routing back to day planner for close-only pass",
        count=len(open_items),
        open=open_items,
    )
    return {
        "close_pass": True,
        "close_pass_attempted": True,
        "is_resuming": True,
        "current_day": total_days,
        "next_event_number": _next_event_number_for_day(prior_events, total_days),
    }
