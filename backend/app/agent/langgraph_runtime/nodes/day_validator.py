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
       - Keep events before the first broken event_number (smart partial retry)
       - Strip from first broken event onward
       - Return errors + first_broken pointer so day_planner re-emits only what changed
       - Do NOT advance current_day
  3. On success (or max attempts exceeded):
       - Emit a `day_end` SSE chunk (instant — no LLM call)
       - Slim prior_events from older completed days to reduce context:
           * Never drop events (avoids phantom-booking state desync)
           * Open openers (no matching closer): keep full
           * Last event of each completed day: keep full
           * Yesterday's events (current_day - 1): keep full (midnight carryover)
           * All other older events: slim to {event_type, event_number, day_number,
                                              day_title, date, name, description}
       - Advance current_day by 1 and reset per-day counters
"""
import re
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


# ─── Prior-events slim helpers ────────────────────────────────────────────────

_SLIM_KEYS = frozenset({
    "event_type", "event_number", "day_number", "date", "name", "description",
})


def _slim_event(event: Dict) -> Dict:
    result = {k: v for k, v in event.items() if k in _SLIM_KEYS and v is not None}
    # Preserve the pairing field used by _compute_open_bookings/_booking_bucket_key
    # so that slimmed openers and closers always land in the same bucket.
    # Without this, a full opener and a slimmed closer (or vice versa) end up in
    # different buckets and the pair appears as a phantom open booking.
    et = event.get("event_type", "")
    if et in ("HOTEL_CHECKIN", "HOTEL_CHECKOUT"):
        field = "hotel_checkin_details" if et == "HOTEL_CHECKIN" else "hotel_checkout_details"
        hotel_name = (event.get(field) or {}).get("hotel_name")
        if hotel_name:
            result[field] = {"hotel_name": hotel_name}
    elif et in ("CAR_PICKUP", "CAR_DROPOFF"):
        field = "car_pickup_details" if et == "CAR_PICKUP" else "car_dropoff_details"
        company = (event.get(field) or {}).get("rental_company_name")
        if company:
            result[field] = {"rental_company_name": company}
    # FLIGHT_TAKEOFF/LAND always bucket to ("FLIGHT", "") — no details needed.
    return result


def _prune_prior_events(prior_events: List[Dict], validated_day: int) -> List[Dict]:
    """
    Slim events from days that are 2+ days before the just-validated day.

    Strategy — never drop events (dropping closers caused phantom open-booking
    state in earlier attempts).  Instead, reduce payload by slimming old event
    objects down to scheduling fields only.

    Rules (applied to each event):
      - day <= 0 or day >= validated_day (current session): keep full
      - day == validated_day - 1 (yesterday): keep full for midnight-carryover context
      - open opener from any older day: keep full (planner needs details to close it)
      - last event of each older completed day: keep full (end-of-day state reference)
      - everything else from older days: slim
    """
    if not prior_events:
        return prior_events

    open_bookings = _compute_open_bookings(prior_events)
    open_opener_keys: set = {
        (item.get("opening_day_number"), item.get("opening_event_number"))
        for item in open_bookings
        if item.get("opening_event_number") is not None
    }

    day_max_evnum: Dict[int, int] = {}
    for e in prior_events:
        dn = e.get("day_number")
        en = e.get("event_number")
        if isinstance(dn, int) and isinstance(en, int):
            if day_max_evnum.get(dn, -1) < en:
                day_max_evnum[dn] = en

    yesterday = validated_day - 1

    result: List[Dict] = []
    for e in prior_events:
        dn = e.get("day_number")
        en = e.get("event_number")

        # Keep special events and anything from today onward untouched
        if not isinstance(dn, int) or dn <= 0 or dn >= validated_day:
            result.append(e)
            continue

        # Keep yesterday's events full (midnight carryover detection in day_planner)
        if dn == yesterday:
            result.append(e)
            continue

        # Older completed day: apply slim-only pruning
        is_open_opener = (dn, en) in open_opener_keys
        is_last_of_day = isinstance(en, int) and day_max_evnum.get(dn) == en

        if is_open_opener or is_last_of_day:
            result.append(e)
        else:
            result.append(_slim_event(e))

    return result


# ─── Smart retry helper ───────────────────────────────────────────────────────

def _find_first_broken_event_number(errors: List[str]) -> int:
    """
    Parse validation error strings to find the minimum event_number that needs
    to be regenerated, so we can keep all good events before that point.

    Error patterns handled:
      - "Timing violation: event #N ..."          → first broken = N
      - "Missing COMMUTE between event #N and event #M ..." → insert at N+1
      - "Missing event_number(s) [X, Y, Z] ..."   → first broken = min(X,Y,Z)
      - "Event #N has day_number=..."              → first broken = N
      - "Duplicate event_number N ..."             → first broken = N
    """
    affected: set = set()
    for err in errors:
        # Timing violation — the starting event is the one with the wrong time
        m = re.match(r'Timing violation: event #(\d+)', err)
        if m:
            affected.add(int(m.group(1)))
            continue
        # Missing COMMUTE between #N and #M → new commute slots in at N+1
        m = re.search(r'Missing COMMUTE between event #(\d+)', err)
        if m:
            affected.add(int(m.group(1)) + 1)
            continue
        # Gap: missing event_number(s) [X, Y, Z]
        m = re.search(r'Missing event_number\(s\) \[([^\]]+)\]', err)
        if m:
            try:
                nums = [int(x.strip()) for x in m.group(1).split(',')]
                affected.update(nums)
            except ValueError:
                pass
            continue
        # Duplicate event_number N
        m = re.search(r'Duplicate event_number (\d+)', err)
        if m:
            affected.add(int(m.group(1)))
            continue
        # Fallback: any "event #N" reference
        for fm in re.finditer(r'event\s+#(\d+)', err, re.IGNORECASE):
            n = int(fm.group(1))
            if n > 0:
                affected.add(n)

    return max(1, min(affected)) if affected else 1


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
            if commute_end - curr_start > timedelta(minutes=10): # 10 minutes tolerance
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
        first_broken = _find_first_broken_event_number(errors)
        # Keep events before the first broken one — only strip from first_broken onward
        good_events = [
            e for e in prior_events
            if e.get("day_number") != current_day
            or (isinstance(e.get("event_number"), int) and e["event_number"] < first_broken)
        ]
        log.warning(
            f"Day {current_day} validation failed (attempt {attempts + 1}/{MAX_VALIDATION_ATTEMPTS})"
            f" — smart retry from event #{first_broken}",
            error_count=len(errors),
            errors=errors,
            first_broken=first_broken,
            kept_events=len(good_events),
            stripped_events=len(prior_events) - len(good_events),
        )
        return {
            "day_validation_errors": error_msg,
            "day_validator_attempts": attempts + 1,
            "next_event_number": first_broken,
            "prior_events": good_events,
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

    # Slim older completed days to keep subsequent planners' context lean.
    # validated_day + 1 = first day that will run next; days < (validated_day)
    # are completed but yesterday (current_day - 1) stays full for midnight-carryover.
    pruned_events = _prune_prior_events(prior_events, validated_day=current_day + 1)
    log.info(
        f"Day {current_day} prior_events after pruning",
        before=len(prior_events),
        after=len(pruned_events),
    )

    return {
        "current_day": current_day + 1,
        "next_event_number": 1,
        "day_validation_errors": None,
        "day_validator_attempts": 0,
        "prior_events": pruned_events,
    }
