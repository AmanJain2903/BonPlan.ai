"""
Event validation helpers — relocated from solo_planner.py.

`validate_itinerary_event(args)` returns (error_str | None, coerced_args | None).
`START_GUARD_MODES` lists modes where re-emitting START is forbidden.
`_compute_open_bookings(events)` returns open opener events with no matching closer.
"""
import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.agent.schemas.structuredOutput import AddItineraryEvent

from app.logging import get_agent_logger

log = get_agent_logger("validator")

# Event type → primary *_details field (regular events).
EVENT_TYPE_TO_DETAIL_FIELD: Dict[str, str] = {
    "START": "start_details",
    "FLIGHT_TAKEOFF": "flight_takeoff_details",
    "FLIGHT_LAND": "flight_land_details",
    "HOTEL_CHECKIN": "hotel_checkin_details",
    "HOTEL_CHECKOUT": "hotel_checkout_details",
    "CAR_PICKUP": "car_pickup_details",
    "CAR_DROPOFF": "car_dropoff_details",
    "DINING": "place_details",
    "ACTIVITY": "place_details",
    "COMMUTE": "commute_details",
    "OTHER": "other_details",
    "END": "end_details",
}

# Event type → anchor *_details field (smart anchor events — all fields Optional).
EVENT_TYPE_TO_ANCHOR_DETAIL_FIELD: Dict[str, str] = {
    "FLIGHT_TAKEOFF": "anchor_flight_takeoff_details",
    "FLIGHT_LAND": "anchor_flight_land_details",
    "HOTEL_CHECKIN": "anchor_hotel_checkin_details",
    "HOTEL_CHECKOUT": "anchor_hotel_checkout_details",
    "CAR_PICKUP": "anchor_car_pickup_details",
    "CAR_DROPOFF": "anchor_car_dropoff_details",
    "DINING": "anchor_place_details",
    "ACTIVITY": "anchor_place_details",
    "OTHER": "anchor_other_details",
}

# All possible detail field names across regular + anchor schemas.
_ALL_POSSIBLE_DETAIL_FIELDS: frozenset = frozenset(
    set(EVENT_TYPE_TO_DETAIL_FIELD.values()) |
    set(EVENT_TYPE_TO_ANCHOR_DETAIL_FIELD.values())
)

# In these modes re-emitting START must be blocked to avoid breaking the frontend.
START_GUARD_MODES = {"editing"}

# ─── Commute-placement validation helpers ────────────────────────────────────
# For every event type, which details field holds it and which sub-fields hold
# the (origin, destination) coordinates. Single-location events repeat the same
# field for both origin and destination.
_SINGLE_LOC_FIELDS: Dict[str, Tuple[str, str]] = {
    "HOTEL_CHECKIN":  ("hotel_checkin_details",  "hotel_coordinates"),
    "HOTEL_CHECKOUT": ("hotel_checkout_details", "hotel_coordinates"),
    "CAR_PICKUP":     ("car_pickup_details",    "pickup_location_coordinates"),
    "CAR_DROPOFF":    ("car_dropoff_details",   "dropoff_location_coordinates"),
    "DINING":         ("place_details",         "coordinates"),
    "ACTIVITY":       ("place_details",         "coordinates"),
    "OTHER":          ("other_details",         "coordinates"),
    "FLIGHT_LAND":    ("flight_land_details",   "arrival_coordinates"),
}
_DUAL_LOC_FIELDS: Dict[str, Tuple[str, str, str]] = {
    # event_type → (details_field, origin_field, destination_field)
    "FLIGHT_TAKEOFF": ("flight_takeoff_details", "departure_coordinates", "arrival_coordinates"),
    "COMMUTE":        ("commute_details",       "origin_coordinates",    "destination_coordinates"),
}
# Adjacent event pairs that DO NOT need a COMMUTE between them even when their
# coordinates differ — the event pair itself represents the transit.
_NATURAL_PAIRS = {
    ("FLIGHT_TAKEOFF", "FLIGHT_LAND"),
}
# Location-mismatch tolerance: two coordinate points within this distance are
# treated as the same place (same airport terminal, same hotel complex, etc.).
_SAME_LOCATION_METERS = 500.0

# ─── Open-booking pairing ────────────────────────────────────────────────────
# Opener event_type → (closer event_type, details field, label field)
_OPEN_CLOSE: Dict[str, Tuple[str, str, str]] = {
    "HOTEL_CHECKIN":  ("HOTEL_CHECKOUT", "hotel_checkin_details",  "hotel_name"),
    "CAR_PICKUP":     ("CAR_DROPOFF",    "car_pickup_details",     "rental_company_name"),
    "FLIGHT_TAKEOFF": ("FLIGHT_LAND",    "flight_takeoff_details", "flight_number"),
}
_CLOSE_TYPES = {close for close, _, _ in _OPEN_CLOSE.values()}

# High-level category for each opener type (used for duplicate-open checks).
_OPENER_CATEGORY: Dict[str, str] = {
    "HOTEL_CHECKIN":  "HOTEL",
    "CAR_PICKUP":     "CAR",
    "FLIGHT_TAKEOFF": "FLIGHT",
}
_CATEGORY_CLOSE_TYPE: Dict[str, str] = {
    "HOTEL": "HOTEL_CHECKOUT",
    "CAR":   "CAR_DROPOFF",
    "FLIGHT": "FLIGHT_LAND",
}


def _booking_bucket_key(event: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Return the (category, sub-key) bucket this event belongs to, or None."""
    et = event.get("event_type")
    if et in ("HOTEL_CHECKIN", "HOTEL_CHECKOUT"):
        field = "hotel_checkin_details" if et == "HOTEL_CHECKIN" else "hotel_checkout_details"
        details = event.get(field) or event.get("anchor_" + field) or {}
        name = (details.get("hotel_name") or "").strip().lower()
        return ("HOTEL", name)
    if et in ("CAR_PICKUP", "CAR_DROPOFF"):
        field = "car_pickup_details" if et == "CAR_PICKUP" else "car_dropoff_details"
        details = event.get(field) or event.get("anchor_" + field) or {}
        name = (details.get("rental_company_name") or "").strip().lower()
        return ("CAR", name)
    if et in ("FLIGHT_TAKEOFF", "FLIGHT_LAND"):
        return ("FLIGHT", "")
    return None


def _compute_open_bookings(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return descriptors for every opener event that has no matching closer yet.

    Events are grouped into (category, sub-key) buckets; within each bucket the
    nth opener (by appearance order) is paired with the nth closer.
    """
    buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}
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

    open_items: List[Dict[str, Any]] = []
    for key, slot in buckets.items():
        for idx, opener in enumerate(slot["openers"]):
            if idx < slot["closers"]:
                continue
            et = opener.get("event_type")
            close_type, open_field, label_key = _OPEN_CLOSE[et]
            details = opener.get(open_field) or opener.get("anchor_" + open_field) or {}
            open_items.append({
                "open_event_type": et,
                "must_be_closed_by": close_type,
                "opening_day_number": opener.get("day_number"),
                "opening_event_number": opener.get("event_number"),
                "label": details.get(label_key) or "",
                "bucket": list(key),
            })
    return open_items


# ─── Time-ordering helpers ────────────────────────────────────────────────────
# Maps event_type → (details_field, start_time_key, end_time_key).
# COMMUTE and START/END are omitted — they have no usable wall-clock times.
_EVENT_TIMES: Dict[str, Tuple[str, str, str]] = {
    "FLIGHT_TAKEOFF": ("flight_takeoff_details", "departure_time", "arrival_time"),
    "FLIGHT_LAND":    ("flight_land_details",    "arrival_time",   "arrival_time"),
    "HOTEL_CHECKIN":  ("hotel_checkin_details",  "checkin_time",   "checkin_time"),
    "HOTEL_CHECKOUT": ("hotel_checkout_details", "checkout_time",  "checkout_time"),
    "CAR_PICKUP":     ("car_pickup_details",     "pickup_time",    "pickup_time"),
    "CAR_DROPOFF":    ("car_dropoff_details",    "dropoff_time",   "dropoff_time"),
    "DINING":         ("place_details",          "start_time",     "end_time"),
    "ACTIVITY":       ("place_details",          "start_time",     "end_time"),
    "OTHER":          ("other_details",          "start_time",     "end_time"),
}

_DT_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d")


def _parse_dt(s: Any) -> Optional[datetime]:
    if not isinstance(s, str):
        return None
    for fmt in _DT_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _event_start_dt(event: Dict[str, Any]) -> Optional[datetime]:
    et = event.get("event_type")
    if et not in _EVENT_TIMES:
        return None
    field, start_key, _ = _EVENT_TIMES[et]
    details = event.get(field) or event.get("anchor_" + field) or {}
    return _parse_dt(details.get(start_key))


def _event_end_dt(event: Dict[str, Any]) -> Optional[datetime]:
    et = event.get("event_type")
    if et not in _EVENT_TIMES:
        return None
    field, _, end_key = _EVENT_TIMES[et]
    details = event.get(field) or event.get("anchor_" + field) or {}
    return _parse_dt(details.get(end_key))


def _latlng(c: Any) -> Optional[Tuple[float, float]]:
    if not isinstance(c, dict):
        return None
    lat = c.get("latitude")
    lng = c.get("longitude")
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def _event_coords(event: Dict[str, Any]) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Return (origin_latlng, destination_latlng) for an event; None if unavailable."""
    et = event.get("event_type")
    if et in _DUAL_LOC_FIELDS:
        field, o_key, d_key = _DUAL_LOC_FIELDS[et]
        details = event.get(field) or event.get("anchor_" + field) or {}
        return _latlng(details.get(o_key)), _latlng(details.get(d_key))
    if et in _SINGLE_LOC_FIELDS:
        field, key = _SINGLE_LOC_FIELDS[et]
        details = event.get(field) or event.get("anchor_" + field) or {}
        c = _latlng(details.get(key))
        return c, c
    return None, None


def _haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lng1 = a
    lat2, lng2 = b
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _same_location(a: Optional[Tuple[float, float]], b: Optional[Tuple[float, float]]) -> bool:
    if a is None or b is None:
        return True  # unknown → don't enforce
    return _haversine_m(a, b) <= _SAME_LOCATION_METERS


def _validate_closer_has_opener(
    args: Dict[str, Any],
    prior_events: List[Dict[str, Any]],
) -> Optional[str]:
    """Block a closer event when there is no matching unclosed opener in prior_events."""
    et = args.get("event_type")
    _CLOSE_TO_OPENER: Dict[str, Tuple[str, str]] = {
        "HOTEL_CHECKOUT": ("HOTEL_CHECKIN",  "HOTEL"),
        "CAR_DROPOFF":    ("CAR_PICKUP",     "CAR"),
        "FLIGHT_LAND":    ("FLIGHT_TAKEOFF", "FLIGHT"),
    }
    if et not in _CLOSE_TO_OPENER:
        return None

    opener_type, _ = _CLOSE_TO_OPENER[et]
    open_items = _compute_open_bookings(prior_events)
    matching = [
        item for item in open_items
        if item.get("open_event_type") == opener_type
    ]
    if matching:
        return None

    log.warning(
        "Agent tried to emit a closer with no matching open opener",
        closer_type=et,
        opener_type=opener_type,
    )
    return (
        f"Cannot emit [{et}]: there is no unclosed [{opener_type}] to close. "
        f"Emit [{opener_type}] first, then close it with [{et}]. "
        "Check prior events — a closer can only follow its matching opener."
    )


def _validate_no_duplicate_open(
    args: Dict[str, Any],
    prior_events: List[Dict[str, Any]],
) -> Optional[str]:
    """Block a new opener when the same category already has an unclosed opener."""
    et = args.get("event_type")
    category = _OPENER_CATEGORY.get(et)
    if category is None:
        return None

    open_items = _compute_open_bookings(prior_events)
    same_cat = [
        item for item in open_items
        if _OPENER_CATEGORY.get(item.get("open_event_type")) == category
    ]
    if not same_cat:
        return None

    existing = same_cat[0]
    close_type = _CATEGORY_CLOSE_TYPE[category]
    label = existing.get("label") or ""
    label_part = f" ({label})" if label else ""
    log.warning(
        "Agent tried to open a booking when same category already open",
        new_event_type=et,
        existing_open=existing,
    )
    return (
        f"Cannot emit [{et}]: there is already an unclosed [{existing['open_event_type']}]{label_part} "
        f"from day {existing['opening_day_number']}, event #{existing['opening_event_number']}. "
        f"A planner must emit [{close_type}] to close it before opening a new one. "
        "Re-emit the appropriate closing event (with the correct day_number and event_number for "
        "the day/position it should have appeared), then re-emit this event."
    )


def _validate_time_order(
    args: Dict[str, Any],
    prior_events: List[Dict[str, Any]],
) -> Optional[str]:
    """Block an event whose start or end time falls before any prior event's end time."""
    day_number = args.get("day_number")
    et = args.get("event_type")
    if et not in _EVENT_TIMES:
        return None

    new_start = _event_start_dt(args)
    new_end = _event_end_dt(args)
    if new_start is None and new_end is None:
        return None

    latest_end: Optional[datetime] = None
    latest_event: Optional[Dict[str, Any]] = None
    for e in prior_events:
        if e.get("day_number") != day_number:
            continue
        e_end = _event_end_dt(e)
        if e_end is not None and (latest_end is None or e_end > latest_end):
            latest_end = e_end
            latest_event = e

    if latest_end is None or latest_event is None:
        return None

    # Determine which new time violates ordering
    start_violates = new_start is not None and new_start < latest_end
    end_violates = new_end is not None and new_end < latest_end
    if not start_violates and not end_violates:
        return None

    violating_time = new_start if start_violates else new_end
    violation_label = "starts" if start_violates else "ends"
    log.warning(
        "Agent emitted event out of chronological order",
        new_event_type=et,
        violating_time=str(violating_time),
        prev_end=str(latest_end),
        prev_event_type=latest_event.get("event_type"),
    )
    return (
        f"Time ordering violation: this [{et}] event {violation_label} at "
        f"{violating_time.strftime('%Y-%m-%dT%H:%M:%S')}, but a prior event "
        f"(day {latest_event.get('day_number')}, event #{latest_event.get('event_number')} "
        f"[{latest_event.get('event_type')}]) already ends at "
        f"{latest_end.strftime('%Y-%m-%dT%H:%M:%S')}. "
        "Events must be strictly chronological. "
        "Either adjust this event's times so it starts >= the previous event's end, "
        f"or re-emit the conflicting prior event (day_number={latest_event.get('day_number')}, "
        f"event_number={latest_event.get('event_number')}) with corrected end time, "
        "followed by any intermediate events, and then this event."
    )


async def _validate_placement(
    args: Dict[str, Any],
    prior_events: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Enforce commute/placement rules for a new itinerary event.
        Between two events on the same day whose locations differ by more than
         `_SAME_LOCATION_METERS`, a COMMUTE must be the bridge.
         Exceptions: the pair is already (FLIGHT_TAKEOFF→FLIGHT_LAND)

    Returns an error string or None.
    """
    et = args.get("event_type")
    current_day = args.get("day_number")

    # START and END have no placement constraints
    if et == "START" or et == "END":
        return None

    prior_day_numbers = [
        e.get("day_number")
        for e in prior_events
        if isinstance(e.get("day_number"), int) and e.get("day_number") > 0
    ]

    if not isinstance(current_day, int) or current_day <= 0:
        return None

    same_day = [e for e in prior_events if e.get("day_number") == current_day]

    # ── Day-boundary check ───────────────────────────────────────────────────
    # When this is the FIRST event of a new day (no same-day prior events) and
    # previous day(s) exist, the traveler must start day N where day N-1
    # ended. Allow a COMMUTE whose origin matches the previous day's end to
    # bridge any location change; anything else is a teleport.
    if not same_day and prior_day_numbers:
        last_prior_day = max(prior_day_numbers)
        prev_day_events = [e for e in prior_events if e.get("day_number") == last_prior_day]
        if prev_day_events:
            prev_day_last = prev_day_events[-1]
            _, prev_day_end = _event_coords(prev_day_last)
            curr_origin, _ = _event_coords(args)
            if not _same_location(prev_day_end, curr_origin):
                log.warning("Agent tried to start a new day at a different location than the previous day's end.")
                return (
                    f"Day {current_day} cannot start at a different location than where "
                    f"day {last_prior_day} ended. The previous day ended at {prev_day_end} "
                    f"(event #{prev_day_last.get('event_number')} "
                    f"[{prev_day_last.get('event_type')}]) but this [{et}] event "
                    f"begins at {curr_origin}. "
                    "Either start this day with a COMMUTE event bridging from "
                    "the previous day's end location, or re-emit the LAST event "
                    f"of day {last_prior_day} (same day_number + event_number as it was for that event) so "
                    "the traveler ends that day at this location. Do NOT teleport."
                )

    # Commute gap between same-day adjacent events at different locations.
    if same_day:
        prev = same_day[-1]
        prev_type = prev.get("event_type")

        # a. When the new event IS a COMMUTE:
        #   • two COMMUTEs in a row are not allowed — if the prior commute was
        #     wrong, the model must re-emit IT (same day_number + event_number)
        #     to overwrite rather than chain another commute.
        #   • its origin must match the prior event's end location, otherwise
        #     the timeline teleports (e.g. prior ended at GGB but this commute
        #     starts at Farley).
        if et == "COMMUTE":
            if prev_type == "COMMUTE":
                log.warning("Agent tried to emit a COMMUTE event back-to-back.")
                return (
                    "Two COMMUTE events back-to-back are not allowed. If the "
                    "previous COMMUTE is wrong, re-emit IT with its original "
                    f"day_number={prev.get('day_number')} and event_number="
                    f"{prev.get('event_number')} to overwrite that event — "
                    "do NOT chain a new commute after it. If this commute even"
                    "is wrong, emit a new event at the same day_number and event_number"
                )
            _, prev_dest = _event_coords(prev)
            curr_origin, _ = _event_coords(args)
            if not _same_location(prev_dest, curr_origin):
                log.warning("Agent tried to emit a COMMUTE event with a mismatched origin.")
                return (
                    f"This COMMUTE event's origin does not match where the traveler "
                    f"currently is according to the last event. Previous event on day {current_day} (event #"
                    f"{prev.get('event_number')} [{prev_type}]) ended at a different "
                    "location than this COMMUTE's origin_coordinates. Fix the "
                    "origin_coordinates / originName to start from the previous "
                    f"event's end location {prev_dest}, then re-emit."
                )
            return None

        # b. Prior event is a COMMUTE — it is itself the bridge, so any next
        # event is acceptable regardless of location.
        if prev_type == "COMMUTE":
            return None

        # c. Natural pairs (flight leg only) don't need a COMMUTE bridge
        # because the takeoff/land events themselves encode the transit.
        if (prev_type, et) in _NATURAL_PAIRS:
            return None

        _, prev_dest = _event_coords(prev)
        curr_origin, _ = _event_coords(args)
        if not _same_location(prev_dest, curr_origin):
            log.warning("Agent tried to emit an event with a mismatched origin.")
            return (
                f"Previous event on day {current_day} (event #{prev.get('event_number')} "
                f"[{prev_type}]) ended at {prev_dest}"
                f"[{et}] event is starting at {curr_origin}. Emit a COMMUTE event first that bridges from the "
                "previous location to this event's location, then re-emit this event."
            )

    return None


async def validate_itinerary_event(
    args: Dict[str, Any],
    mode: str = "autonomous",
    is_resuming: bool = False,
    prior_events: Optional[List[Dict[str, Any]]] = None,
    current_day: int = 0,
    total_days: int = 1,
    next_event_number: int = 1,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate and coerce an add_itinerary_event call.

    Returns:
        (None, coerced_args)  on success
        (error_str, None)     on failure
    """
    event_type = args.get("event_type", "")

    # ── day_number / event_number sanity checks ───────────────────────────
    day_number = args.get("day_number")
    event_number = args.get("event_number")

    if day_number is None or not isinstance(day_number, int):
        log.warning("Missing or non-int day_number", day_number=day_number)
        return (
            "day_number is required and must be an integer. "
            "For START use 0, for END use -1, for regular events use the "
            f"current day number which is {current_day}.",
            None,
        )

    if event_number is None or not isinstance(event_number, int):
        log.warning("Missing or non-int event_number", event_number=event_number)
        return (
            "event_number is required and must be an integer. "
            "For START use 0, for END use -1, for regular events the next "
            f"expected event_number is {next_event_number}.",
            None,
        )

    # START and END have fixed numbering enforced upstream, but double-check.
    if event_type == "START":
        if day_number != 0 or event_number != 0:
            log.warning("START event with wrong numbering", day_number=day_number, event_number=event_number)
            args["day_number"] = 0
            args["event_number"] = 0
    elif event_type == "END":
        if day_number != -1 or event_number != -1:
            log.warning("END event with wrong numbering", day_number=day_number, event_number=event_number)
            args["day_number"] = -1
            args["event_number"] = -1
    else:
        # Regular events: day_number must be >= 1, event_number >= 1.
        if day_number < 1:
            log.warning("Regular event with invalid day_number", event_type=event_type, day_number=day_number)
            return (
                f"day_number must be >= 1 for event_type='{event_type}', "
                f"but got {day_number}. The current day is {current_day}.",
                None,
            )
        if event_number < 1:
            log.warning("Regular event with invalid event_number", event_type=event_type, event_number=event_number)
            return (
                f"event_number must be >= 1 for event_type='{event_type}', "
                f"but got {event_number}. The next expected event_number is "
                f"{next_event_number}.",
                None,
            )
        
        if total_days > 0 and day_number > total_days:
            log.warning(
                "day_number exceeds total_days",
                event_type=event_type,
                day_number=day_number,
                total_days=total_days,
            )
            return (
                f"day_number={day_number} exceeds the total trip length of "
                f"{total_days} days. You cannot emit events beyond the trip.",
                None,
            )

    # ── Mode guards ───────────────────────────────────────────────────────
    # Editing-mode guard: START re-emission breaks the frontend.
    if mode in START_GUARD_MODES and event_type == "START":
        log.warning(f"Agent tried to re-emit a START event in {mode} mode.")
        return (
            "Re-emitting a START event is forbidden in editing mode. "
            "Edit individual events using their day_number/event_number instead.",
            None,
        )

    # Resume guard: once START has been emitted in a prior run, re-emitting
    # it corrupts the frontend timeline. This applies to every mode.
    if is_resuming and event_type == "START":
        log.warning("Agent tried to re-emit a START event in a resuming run.")
        return (
            "A START event was already emitted in a previous run. You are "
            "resuming an existing itinerary — DO NOT emit START again. "
            "Continue chronologically from the last emitted event.",
            None,
        )

    # ── event_type + detail-field shape checks ────────────────────────────
    expected_field = EVENT_TYPE_TO_DETAIL_FIELD.get(event_type)
    if not expected_field:
        log.warning("Agent tried to emit an unknown event_type.", event_type=event_type)
        return f"Unknown event_type '{event_type}'.", None

    anchor_field = EVENT_TYPE_TO_ANCHOR_DETAIL_FIELD.get(event_type)
    allowed_fields = {f for f in (expected_field, anchor_field) if f}

    populated_detail_fields = [
        f for f in _ALL_POSSIBLE_DETAIL_FIELDS if args.get(f) is not None
    ]

    if not any(f in allowed_fields for f in populated_detail_fields):
        log.warning("Agent tried to emit an event_type with a missing detail field.", event_type=event_type)
        anchor_hint = f" or '{anchor_field}' (for anchor events)" if anchor_field else ""
        return (
            f"event_type='{event_type}' requires '{expected_field}'{anchor_hint} to be populated, "
            f"but it is missing or null.",
            None,
        )

    extra_fields = [f for f in populated_detail_fields if f not in allowed_fields]
    if extra_fields:
        log.warning("Agent tried to emit an event_type with extra detail fields.", event_type=event_type)
        return (
            f"event_type='{event_type}' must have ONLY "
            + " or ".join(f"'{f}'" for f in sorted(allowed_fields))
            + f" populated, but also received: {extra_fields}.",
            None,
        )

    # Closer-without-opener guard: block closer (FLIGHT_LAND / HOTEL_CHECKOUT /
    # CAR_DROPOFF) when no matching opener is currently open.
    closer_no_opener_error = _validate_closer_has_opener(args, prior_events or [])
    if closer_no_opener_error:
        return closer_no_opener_error, None

    # Duplicate-open guard: block opener when same category already has unclosed opener.
    dup_open_error = _validate_no_duplicate_open(args, prior_events or [])
    if dup_open_error:
        return dup_open_error, None

    # Chronological time-order guard: block event that predates a prior event's end.
    time_order_error = _validate_time_order(args, prior_events or [])
    if time_order_error:
        return time_order_error, None

    # Commute/placement rules — only after basic shape passes.
    placement_error = await _validate_placement(args, prior_events or [])
    if placement_error:
        return placement_error, None

    try:
        validated = AddItineraryEvent(**args)
        return None, validated.model_dump()
    except Exception as exc:
        log.error("Validation failed", error=str(exc))
        return str(exc), None
