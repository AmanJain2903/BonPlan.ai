"""
Day validator node.

Runs after every day_planner invocation (for each day including close-pass days).
Responsibilities:
  1. Validate all events emitted for current_day:
       a. day_number correctness
       b. sequential event_number (no gaps/duplicates)
       c. missing-commute check (second pass after real-time validator)
       d. timing correctness including commute duration (durationSeconds)
  2. On validation failure (and attempts < MAX_VALIDATION_ATTEMPTS):
       - Strip current_day events from prior_events
       - Return errors to state so day_planner includes them in next prompt
       - Do NOT advance current_day
  3. On success (or max attempts exceeded):
       - Emit a `day_end` SSE chunk (instant — no LLM call)
       - Prune prior_events to minimise context passed to subsequent planners:
           * Open openers (no matching closer): keep full
           * Last event per day: keep full
           * Closers (HOTEL_CHECKOUT, CAR_DROPOFF, FLIGHT_LAND): drop
           * Closed opener+closer pairs: drop both sides
           * All other events: slim {event_type, event_number, day_number,
                                     day_title, date, name, description}
       - Advance current_day by 1 and reset per-day counters
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.streaming import emit
from app.agent.langgraph_runtime.validator import (
    _compute_open_bookings,
    _event_start_dt,
    _event_end_dt,
    _event_coords,
    _same_location,
    _NATURAL_PAIRS,
    EVENT_TYPE_TO_DETAIL_FIELD,
)

log = get_agent_logger("day_validator")

MAX_VALIDATION_ATTEMPTS = 2  # after this many failures, advance anyway

_CLOSER_TYPES = {"HOTEL_CHECKOUT", "CAR_DROPOFF", "FLIGHT_LAND"}
_OPENER_TYPES = {"HOTEL_CHECKIN", "CAR_PICKUP", "FLIGHT_TAKEOFF"}
_SPECIAL_TYPES = {"START", "END"}


# ─── Slim-event helper ───────────────────────────────────────────────────────

def _slim_event(e: Dict[str, Any]) -> Dict[str, Any]:
    """Return a minimal summary dict for an event (no coordinates or cost data)."""
    et = e.get("event_type", "")
    details_field = EVENT_TYPE_TO_DETAIL_FIELD.get(et, "")
    details: Dict = e.get(details_field) or {} if details_field else {}

    name = (
        details.get("hotel_name")
        or details.get("place_name")
        or details.get("event_name")
        or details.get("rental_company_name")
        or details.get("flight_number")
        or ""
    )
    description = (
        details.get("event_description")
        or details.get("summary")
        or details.get("description")
        or ""
    )

    return {
        "event_type": et,
        "event_number": e.get("event_number"),
        "day_number": e.get("day_number"),
        "day_title": e.get("day_title") or "",
        "date": e.get("date") or "",
        "name": name,
        "description": description,
    }


# ─── Pruning ─────────────────────────────────────────────────────────────────

def _prune_prior_events(all_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Prune the full prior_events list after a day completes.

    Rules applied across ALL events (not just the current day) so that opener
    events from earlier days which became closed today are also compacted:

    1. SPECIAL (START/END): keep full.
    2. CLOSER types: always drop.
    3. OPENER types with no matching closer (open_keys): keep full.
    4. OPENER types that are now closed (not in open_keys): slim.
    5. Last event of each real day: keep full.
    6. Everything else: slim.
    """
    # Which openers still have no matching closer across all events
    open_bookings = _compute_open_bookings(all_events)
    open_keys = {
        (b["opening_day_number"], b["opening_event_number"])
        for b in open_bookings
    }

    # Last event_number per real day
    last_per_day: Dict[int, int] = {}
    for e in all_events:
        d = e.get("day_number")
        n = e.get("event_number") or 0
        if isinstance(d, int) and d > 0:
            if d not in last_per_day or n > last_per_day[d]:
                last_per_day[d] = n
    last_event_keys = {(d, n) for d, n in last_per_day.items()}

    pruned: List[Dict[str, Any]] = []
    for e in all_events:
        et = e.get("event_type")
        key = (e.get("day_number"), e.get("event_number"))

        if et in _SPECIAL_TYPES:
            pruned.append(e)
            continue

        if et == "COMMUTE":
            # Drop COMMUTE events entirely
            continue

        if et in _CLOSER_TYPES:
            # Drop closers entirely
            continue

        if key in open_keys:
            # Open opener — keep full so later planners know to close it
            pruned.append(e)
            continue

        if key in last_event_keys:
            # Last event of any day — keep full for cross-day placement checks
            pruned.append(e)
            continue

        pruned.append(_slim_event(e))

    return pruned


# ─── Validation helpers ───────────────────────────────────────────────────────

def _check_day_numbers(day_events: List[Dict], current_day: int) -> List[str]:
    errors: List[str] = []
    for e in day_events:
        if e.get("day_number") != current_day:
            errors.append(
                f"Event #{e.get('event_number')} has day_number="
                f"{e.get('day_number')}, expected {current_day}."
            )
    return errors


def _check_sequential_numbers(day_events: List[Dict]) -> List[str]:
    """Events must be numbered 1, 2, 3, … with no gaps or duplicates."""
    errors: List[str] = []
    seen: Dict[int, int] = {}  # event_number → count
    for e in day_events:
        n = e.get("event_number")
        if not isinstance(n, int) or n < 1:
            errors.append(
                f"Event with type '{e.get('event_type')}' has invalid "
                f"event_number={n!r}. Must be an integer >= 1."
            )
            continue
        seen[n] = seen.get(n, 0) + 1

    if not seen:
        return errors

    for n, count in seen.items():
        if count > 1:
            errors.append(f"Duplicate event_number {n} appears {count} times.")

    expected = 1
    for n in sorted(seen):
        if n > expected:
            missing = list(range(expected, n))
            errors.append(
                f"Missing event_number(s) {missing} — gap before event #{n}."
            )
        expected = n + 1

    return errors


def _check_commute_gaps(day_events: List[Dict]) -> List[str]:
    """Second-pass commute-gap check (real-time validator already blocked most cases)."""
    errors: List[str] = []
    for i in range(1, len(day_events)):
        prev = day_events[i - 1]
        curr = day_events[i]
        prev_type = prev.get("event_type")
        curr_type = curr.get("event_type")

        # Natural pairs don't need commute between them
        if (prev_type, curr_type) in _NATURAL_PAIRS:
            continue
        # A commute is itself the bridge
        if prev_type == "COMMUTE" or curr_type == "COMMUTE":
            continue

        _, prev_dest = _event_coords(prev)
        curr_origin, _ = _event_coords(curr)
        if not _same_location(prev_dest, curr_origin):
            errors.append(
                f"Missing COMMUTE between event #{prev.get('event_number')} "
                f"[{prev_type}] and event #{curr.get('event_number')} [{curr_type}]: "
                f"locations differ ({prev_dest} → {curr_origin}) but no COMMUTE bridges them."
            )
    return errors


def _check_timing(day_events: List[Dict]) -> List[str]:
    """
    Check that each event starts after the previous one ends, accounting for
    COMMUTE duration (CommuteEventDetails.durationSeconds).

    For a COMMUTE event: since it has no explicit start_time field, we treat its
    start as the previous event's end time. Therefore the event AFTER the commute
    must start at or after (prev_event_end + durationSeconds).
    """
    errors: List[str] = []
    for i in range(1, len(day_events)):
        prev = day_events[i - 1]
        curr = day_events[i]
        curr_start = _event_start_dt(curr)
        if curr_start is None:
            continue

        if prev.get("event_type") == "COMMUTE":
            # Need the event before the commute to compute commute end
            if i < 2:
                continue
            pre_commute = day_events[i - 2]
            pre_end = _event_end_dt(pre_commute)
            duration_s = float((prev.get("commute_details") or {}).get("durationSeconds") or 0)
            if pre_end is None:
                continue
            commute_end = pre_end + timedelta(seconds=duration_s)
            if curr_start < commute_end:
                errors.append(
                    f"Timing violation: event #{curr.get('event_number')} "
                    f"[{curr.get('event_type')}] starts at "
                    f"{curr_start.strftime('%Y-%m-%dT%H:%M:%S')} but commute "
                    f"#{prev.get('event_number')} ends at "
                    f"{commute_end.strftime('%Y-%m-%dT%H:%M:%S')} "
                    f"(prev event ends {pre_end.strftime('%Y-%m-%dT%H:%M:%S')} "
                    f"+ {int(duration_s)}s). Adjust the start time or commute duration."
                )
        else:
            prev_end = _event_end_dt(prev)
            if prev_end is None:
                continue
            if curr_start < prev_end:
                errors.append(
                    f"Timing violation: event #{curr.get('event_number')} "
                    f"[{curr.get('event_type')}] starts at "
                    f"{curr_start.strftime('%Y-%m-%dT%H:%M:%S')} but event "
                    f"#{prev.get('event_number')} [{prev.get('event_type')}] "
                    f"ends at {prev_end.strftime('%Y-%m-%dT%H:%M:%S')}."
                )
    return errors


def _validate_day_events(day_events: List[Dict], current_day: int) -> List[str]:
    """Run all validation checks and return accumulated error strings."""
    errors: List[str] = []
    errors.extend(_check_day_numbers(day_events, current_day))
    errors.extend(_check_sequential_numbers(day_events))
    errors.extend(_check_commute_gaps(day_events))
    errors.extend(_check_timing(day_events))
    return errors


# ─── Node ────────────────────────────────────────────────────────────────────

async def day_validator_node(state: PlannerState) -> Dict[str, Any]:
    current_day = state.get("current_day", 1)
    total_days = state.get("total_days", 1)
    attempts = state.get("day_validator_attempts", 0)
    prior_events: List[Dict] = list(state.get("prior_events") or [])

    run_id = (
        (state.get("trip_id") + "-" + state.get("user_id"))
        if state.get("user_id") and state.get("trip_id")
        else str(uuid.uuid4())
    )
    set_agent_log_context(run_id=run_id, node="day_validator", day=current_day)

    # Extract this day's events, sorted chronologically
    day_events = sorted(
        [e for e in prior_events if e.get("day_number") == current_day],
        key=lambda e: e.get("event_number") or 0,
    )

    errors = _validate_day_events(day_events, current_day)

    # ── Retry path ────────────────────────────────────────────────────────────
    if errors and attempts < MAX_VALIDATION_ATTEMPTS:
        error_msg = "\n".join(f"- {e}" for e in errors)
        log.warning(
            f"Day {current_day} validation failed (attempt {attempts + 1}/{MAX_VALIDATION_ATTEMPTS})",
            error_count=len(errors),
            errors=errors,
        )
        # Strip current day's events so day_planner re-emits them from scratch
        stripped = [e for e in prior_events if e.get("day_number") != current_day]
        return {
            "day_validation_errors": error_msg,
            "day_validator_attempts": attempts + 1,
            "next_event_number": 1,
            "prior_events": stripped,
        }

    # ── Success / max-attempts path ────────────────────────────────────────────
    if errors:
        log.warning(
            f"Day {current_day} max validation attempts reached — proceeding anyway",
            error_count=len(errors),
            errors=errors,
        )
    else:
        log.info(f"Day {current_day} validated successfully", event_count=len(day_events))

    # Emit lightweight day_end signal — no LLM call, instant
    emit({"type": "day_end", "day_number": current_day})

    # Prune for context window before handing off to the next node
    pruned = _prune_prior_events(prior_events)

    return {
        "current_day": current_day + 1,
        "next_event_number": 1,
        "day_validation_errors": None,
        "day_validator_attempts": 0,
        "prior_events": pruned,
    }
