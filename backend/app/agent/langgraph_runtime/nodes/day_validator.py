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
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

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
    "event_type", "event_number", "day_number", "date", "name", "description", "place_id",
    "is_locked",
})


def _slim_event(event: Dict) -> Dict:
    result = {k: v for k, v in event.items() if k in _SLIM_KEYS and v is not None}
    # Preserve the pairing field used by _compute_open_bookings/_booking_bucket_key
    # so that slimmed openers and closers always land in the same bucket.
    # Check both regular and anchor variants (anchor events use anchor_* fields).
    et = event.get("event_type", "")
    if et in ("HOTEL_CHECKIN", "HOTEL_CHECKOUT"):
        base = "hotel_checkin_details" if et == "HOTEL_CHECKIN" else "hotel_checkout_details"
        for fn in (base, "anchor_" + base):
            hotel_name = (event.get(fn) or {}).get("hotel_name")
            if hotel_name:
                result[fn] = {"hotel_name": hotel_name}
                break
    elif et in ("CAR_PICKUP", "CAR_DROPOFF"):
        base = "car_pickup_details" if et == "CAR_PICKUP" else "car_dropoff_details"
        for fn in (base, "anchor_" + base):
            company = (event.get(fn) or {}).get("rental_company_name")
            if company:
                result[fn] = {"rental_company_name": company}
                break
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


def _normalize_venue_name(name: str) -> str:
    """Lowercase, strip punctuation, drop leading articles for fuzzy name comparison."""
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    for prefix in ("the ", "a ", "an "):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


def _check_duplicate_venues(
    day_events: List[Dict], prior_events: List[Dict], current_day: int
) -> List[str]:
    """
    Flag ACTIVITY or DINING venues scheduled more than once:
      - Cross-day: same venue already appeared in a prior day's events.
      - Within-day: same venue appears twice in current day (e.g. lunch + dinner same spot).
    HOTEL_CHECKIN/CHECKOUT and COMMUTE are intentionally excluded.
    """
    errors: List[str] = []
    _dedup_types = {"ACTIVITY", "DINING"}

    # Build prior-day seen sets
    prior_pids: set = set()
    prior_names: dict = {}  # norm_name → (day_number, original_name)
    for ev in prior_events:
        if ev.get("day_number") == current_day:
            continue
        if (ev.get("event_type") or "") not in _dedup_types:
            continue
        pid = (ev.get("place_id") or "").strip()
        name = (ev.get("name") or "").strip()
        if pid:
            prior_pids.add(pid)
        if name:
            norm = _normalize_venue_name(name)
            if norm and norm not in prior_names:
                prior_names[norm] = (ev.get("day_number", "?"), name)

    # Within-day seen sets (populated as we scan today's events in order)
    day_pids: dict = {}   # pid → event_number
    day_names: dict = {}  # norm_name → event_number

    for ev in day_events:
        etype = (ev or {}).get("event_type", "")
        if etype not in _dedup_types:
            continue
        pid = (ev.get("place_id") or "").strip()
        name = (ev.get("name") or "").strip()
        ev_num = ev.get("event_number")
        norm = _normalize_venue_name(name)

        # Cross-day duplicate check (place_id wins; fall back to normalized name)
        if pid and pid in prior_pids:
            errors.append(
                f"Duplicate venue: event #{ev_num} [{etype}] '{name}' (place_id={pid}) "
                f"already scheduled on a prior day. Choose a different venue."
            )
            continue
        if norm and norm in prior_names:
            prior_day, prior_name = prior_names[norm]
            errors.append(
                f"Duplicate venue: event #{ev_num} [{etype}] '{name}' matches "
                f"'{prior_name}' from Day {prior_day}. Choose a different venue."
            )
            continue

        # Within-day duplicate check
        if pid and pid in day_pids:
            errors.append(
                f"Duplicate venue within Day {current_day}: event #{ev_num} [{etype}] "
                f"'{name}' same place as event #{day_pids[pid]}. "
                f"Do not visit the same venue twice in one day."
            )
        elif norm and norm in day_names:
            errors.append(
                f"Duplicate venue within Day {current_day}: event #{ev_num} [{etype}] "
                f"'{name}' matches event #{day_names[norm]} in same day. "
                f"Do not visit the same venue twice in one day."
            )
        else:
            if pid:
                day_pids[pid] = ev_num
            if norm:
                day_names[norm] = ev_num

    return errors


_DOW_WEEKDAYS = {0, 1, 2, 3, 4}
_DOW_WEEKENDS = {5, 6}


def _trip_day_date(start_date: dict, current_day: int) -> Optional[date]:
    try:
        return date(start_date["year"], start_date["month"], start_date["day"]) + timedelta(days=current_day - 1)
    except (KeyError, TypeError, ValueError):
        return None


def _hhmm_to_minutes(t: str) -> Optional[int]:
    try:
        h, m = map(int, t.split(":"))
        return h * 60 + m
    except Exception:
        return None


def _event_start_hhmm(event: Dict) -> Optional[int]:
    """Extract start time as total minutes from event details (regular or anchor)."""
    for field in (
        "place_details", "anchor_place_details",
        "other_details", "anchor_other_details",
        "flight_takeoff_details", "anchor_flight_takeoff_details",
        "car_pickup_details", "anchor_car_pickup_details",
        "hotel_checkin_details", "anchor_hotel_checkin_details",
    ):
        det = event.get(field) or {}
        st = det.get("start_time") or det.get("departure_time") or det.get("checkin_time") or det.get("pickup_time")
        if st:
            try:
                parts = st.split("T")
                time_part = parts[1] if len(parts) > 1 else parts[0]
                hh, mm = int(time_part[:2]), int(time_part[3:5])
                return hh * 60 + mm
            except Exception:
                pass
    return None


def _check_smart_anchors(
    day_events: List[Dict],
    smart_anchors: List[Dict],
    current_day: int,
    trip_start: dict,
) -> List[str]:
    """Verify all smart anchors expected on this day appear in day_events."""
    errors: List[str] = []
    current_date_obj = _trip_day_date(trip_start, current_day)
    if current_date_obj is None:
        return errors
    current_date_str = current_date_obj.isoformat()

    for anchor in smart_anchors:
        atype = anchor.get("type", "")
        inputs = anchor.get("user_inputs") or {}
        start_t = anchor.get("start_time") or inputs.get("start_time")

        if atype == "FLIGHT":
            if inputs.get("departure_date") != current_date_str:
                continue
            has_takeoff = any(e.get("event_type") == "FLIGHT_TAKEOFF" for e in day_events)
            if not has_takeoff:
                airline = inputs.get("airline", "")
                fnum = inputs.get("flight_number", "")
                label = f"{airline} {fnum}".strip() or "flight"
                errors.append(
                    f"Smart anchor FLIGHT ({label}) was not emitted for Day {current_day}. "
                    "FLIGHT_TAKEOFF event is required."
                )

        elif atype == "HOTEL":
            checkin = inputs.get("checkin_date", "")
            checkout = inputs.get("checkout_date", "")
            hotel = inputs.get("hotel_name", "hotel")
            if checkin == current_date_str:
                if not any(e.get("event_type") == "HOTEL_CHECKIN" for e in day_events):
                    errors.append(
                        f"Smart anchor HOTEL CHECKIN ({hotel}) was not emitted for Day {current_day}. "
                        "HOTEL_CHECKIN event is required."
                    )
            if checkout == current_date_str:
                if not any(e.get("event_type") == "HOTEL_CHECKOUT" for e in day_events):
                    errors.append(
                        f"Smart anchor HOTEL CHECKOUT ({hotel}) was not emitted for Day {current_day}. "
                        "HOTEL_CHECKOUT event is required."
                    )

        elif atype == "CAR_RENTAL":
            pickup = inputs.get("pickup_date", "")
            dropoff = inputs.get("dropoff_date", "")
            company = inputs.get("company", "rental car")
            if pickup == current_date_str:
                if not any(e.get("event_type") == "CAR_PICKUP" for e in day_events):
                    errors.append(
                        f"Smart anchor CAR PICKUP ({company}) was not emitted for Day {current_day}. "
                        "CAR_PICKUP event is required."
                    )
            if dropoff == current_date_str:
                if not any(e.get("event_type") == "CAR_DROPOFF" for e in day_events):
                    errors.append(
                        f"Smart anchor CAR DROPOFF ({company}) was not emitted for Day {current_day}. "
                        "CAR_DROPOFF event is required."
                    )

        elif atype in ("ACTIVITY", "DINING", "OTHER"):
            if inputs.get("date") != current_date_str:
                continue
            name = inputs.get("name", "")
            type_map = {"ACTIVITY": "ACTIVITY", "DINING": "DINING", "OTHER": "OTHER"}
            etype = type_map[atype]
            matching_events = [e for e in day_events if e.get("event_type") == etype]
            if not matching_events:
                errors.append(
                    f"Smart anchor {etype} '{name}' was not emitted for Day {current_day}. "
                    f"An {etype} event is required on this day."
                )
                continue
            # If exact time required, verify timing
            if start_t:
                anchor_min = _hhmm_to_minutes(start_t)
                if anchor_min is not None:
                    found_timing = False
                    for ev in matching_events:
                        ev_min = _event_start_hhmm(ev)
                        if ev_min is not None and abs(ev_min - anchor_min) <= 15:
                            found_timing = True
                            break
                    if not found_timing:
                        errors.append(
                            f"Smart anchor {etype} '{name}' must start at {start_t} "
                            f"(±15 min) but no matching {etype} event found at that time on Day {current_day}."
                        )

    return errors


def _check_locked_routines(
    day_events: List[Dict],
    locked_routines: List[Dict],
    current_day: int,
    trip_start: dict,
) -> List[str]:
    """Verify all locked routines applicable to this day appear as OTHER events."""
    errors: List[str] = []
    current_date_obj = _trip_day_date(trip_start, current_day)
    if current_date_obj is None:
        return errors
    dow = current_date_obj.weekday()

    for routine in locked_routines:
        freq = routine.get("frequency", "daily")
        specific = routine.get("specific_days") or []
        if freq == "daily":
            applies = True
        elif freq == "weekdays":
            applies = dow in _DOW_WEEKDAYS
        elif freq == "weekends":
            applies = dow in _DOW_WEEKENDS
        elif freq == "specific_days":
            applies = dow in specific
        else:
            applies = False
        if not applies:
            continue

        name = routine.get("name", "routine")
        start_t = routine.get("start_time", "")
        dur = routine.get("duration_minutes", 30)
        anchor_min = _hhmm_to_minutes(start_t) if start_t else None

        other_events = [e for e in day_events if e.get("event_type") == "OTHER"]
        if not other_events:
            errors.append(
                f"Locked routine '{name}' ({start_t}, {dur} min) was not emitted for Day {current_day}. "
                "Emit as OTHER event at the specified time."
            )
            continue

        if anchor_min is not None:
            found = any(
                _event_start_hhmm(e) is not None and abs((_event_start_hhmm(e) or 0) - anchor_min) <= 15
                for e in other_events
            )
            if not found:
                errors.append(
                    f"Locked routine '{name}' must appear as OTHER event at {start_t} "
                    f"(±15 min) on Day {current_day}, but no matching OTHER event found at that time."
                )

    return errors


def _annotate_is_locked(
    prior_events: List[Dict],
    smart_anchors: List[Dict],
    locked_routines: List[Dict],
    trip_start: dict,
) -> List[Dict]:
    """
    Set is_locked=True on events that came from smart anchors or locked routines.
    All other non-structural events get is_locked=False.
    Structural events (START/END/COMMUTE) are skipped.
    """
    _structural = {"START", "END", "COMMUTE"}

    # Pre-compute which (day, event_type) combos are anchor-sourced
    anchor_day_types: Dict[int, Set[str]] = {}  # day_number → set of event_types

    for anchor in smart_anchors:
        atype = anchor.get("type", "")
        inputs = anchor.get("user_inputs") or {}

        def _date_to_day(date_str: str) -> Optional[int]:
            if not date_str:
                return None
            try:
                d = date.fromisoformat(date_str)
                base = date(trip_start["year"], trip_start["month"], trip_start["day"])
                diff = (d - base).days + 1
                return diff if diff >= 1 else None
            except Exception:
                return None

        if atype == "FLIGHT":
            day = _date_to_day(inputs.get("departure_date", ""))
            if day:
                anchor_day_types.setdefault(day, set()).update({"FLIGHT_TAKEOFF", "FLIGHT_LAND"})
        elif atype == "HOTEL":
            cin_day = _date_to_day(inputs.get("checkin_date", ""))
            cout_day = _date_to_day(inputs.get("checkout_date", ""))
            if cin_day:
                anchor_day_types.setdefault(cin_day, set()).add("HOTEL_CHECKIN")
            if cout_day:
                anchor_day_types.setdefault(cout_day, set()).add("HOTEL_CHECKOUT")
        elif atype == "CAR_RENTAL":
            pu_day = _date_to_day(inputs.get("pickup_date", ""))
            do_day = _date_to_day(inputs.get("dropoff_date", ""))
            if pu_day:
                anchor_day_types.setdefault(pu_day, set()).add("CAR_PICKUP")
            if do_day:
                anchor_day_types.setdefault(do_day, set()).add("CAR_DROPOFF")
        elif atype in ("ACTIVITY", "DINING", "OTHER"):
            day = _date_to_day(inputs.get("date", ""))
            if day:
                etype = {"ACTIVITY": "ACTIVITY", "DINING": "DINING", "OTHER": "OTHER"}[atype]
                anchor_day_types.setdefault(day, set()).add(etype)

    # Pre-compute routine (day, start_min) pairs
    routine_day_times: Dict[int, List[int]] = {}  # day_number → [start_minutes]
    total_days_approx = max((e.get("day_number") or 0) for e in prior_events) if prior_events else 0

    for routine in locked_routines:
        freq = routine.get("frequency", "daily")
        specific = routine.get("specific_days") or []
        start_t = routine.get("start_time", "")
        anchor_min = _hhmm_to_minutes(start_t)
        if anchor_min is None:
            continue
        for day_n in range(1, total_days_approx + 1):
            day_date = _trip_day_date(trip_start, day_n)
            if day_date is None:
                continue
            dow = day_date.weekday()
            if freq == "daily":
                applies = True
            elif freq == "weekdays":
                applies = dow in _DOW_WEEKDAYS
            elif freq == "weekends":
                applies = dow in _DOW_WEEKENDS
            elif freq == "specific_days":
                applies = dow in specific
            else:
                applies = False
            if applies:
                routine_day_times.setdefault(day_n, []).append(anchor_min)

    result: List[Dict] = []
    for event in prior_events:
        event = dict(event)
        etype = event.get("event_type", "")
        day_n = event.get("day_number")

        if etype in _structural or not isinstance(day_n, int) or day_n <= 0:
            result.append(event)
            continue

        # Check anchor match
        is_anchor = etype in (anchor_day_types.get(day_n) or set())

        # Check routine match (OTHER events with matching start time)
        is_routine = False
        if etype == "OTHER" and day_n in routine_day_times:
            ev_min = _event_start_hhmm(event)
            if ev_min is not None:
                is_routine = any(abs(ev_min - rm) <= 15 for rm in routine_day_times[day_n])

        event["is_locked"] = is_anchor or is_routine
        result.append(event)

    return result


def _validate_day_events(
    day_events: List[Dict],
    current_day: int,
    prior_events: Optional[List[Dict]] = None,
    smart_anchors: Optional[List[Dict]] = None,
    locked_routines: Optional[List[Dict]] = None,
    trip_start: Optional[dict] = None,
) -> List[str]:
    """Run all validation checks and return accumulated error strings."""
    errors: List[str] = []
    errors.extend(_check_day_numbers(day_events, current_day))
    errors.extend(_check_sequential_numbers(day_events))
    errors.extend(_check_commute_gaps(day_events))
    errors.extend(_check_timing(day_events))
    errors.extend(_check_duplicate_venues(day_events, prior_events or [], current_day))
    if smart_anchors and trip_start:
        errors.extend(_check_smart_anchors(day_events, smart_anchors, current_day, trip_start))
    if locked_routines and trip_start:
        errors.extend(_check_locked_routines(day_events, locked_routines, current_day, trip_start))
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

    trip_input = state.get("trip_input") or {}
    smart_anchors: List[Dict] = trip_input.get("smart_anchors") or []
    locked_routines: List[Dict] = (trip_input.get("preferences") or {}).get("locked_routines") or []
    trip_start: dict = trip_input.get("start_date") or {}

    # Extract this day's events, sorted chronologically
    day_events = sorted(
        [e for e in prior_events if e.get("day_number") == current_day],
        key=lambda e: e.get("event_number") or 0,
    )

    errors = _validate_day_events(
        day_events, current_day, prior_events,
        smart_anchors=smart_anchors,
        locked_routines=locked_routines,
        trip_start=trip_start,
    )

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
        emit({
            "type": "events_removed",
            "day_number": current_day,
            "from_event_number": first_broken,
            "reason": "validation_retry",
        })
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

    # Annotate is_locked on all events based on anchor/routine matches.
    annotated_events = _annotate_is_locked(prior_events, smart_anchors, locked_routines, trip_start)

    # Emit lock annotations for this day so the DB writer can persist them.
    # _apply_event_write saved events with is_locked=None; this corrects the DB.
    lock_updates = [
        {"day_number": e["day_number"], "event_number": e["event_number"], "is_locked": e.get("is_locked")}
        for e in annotated_events
        if isinstance(e.get("day_number"), int) and e.get("day_number") == current_day
        and e.get("is_locked") is not None
    ]
    if lock_updates:
        emit({"type": "lock_update", "updates": lock_updates})

    # Slim older completed days to keep subsequent planners' context lean.
    # validated_day + 1 = first day that will run next; days < (validated_day)
    # are completed but yesterday (current_day - 1) stays full for midnight-carryover.
    pruned_events = _prune_prior_events(annotated_events, validated_day=current_day + 1)
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
