"""
Event validation helpers — relocated from solo_planner.py.

`validate_itinerary_event(args)` returns (error_str | None, coerced_args | None).
`START_GUARD_MODES` lists modes where re-emitting START is forbidden.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

from app.agent.schemas.structuredOutput import AddItineraryEvent

from app.logging import get_agent_logger

log = get_agent_logger("validator")

# Event type → the single *_details field that MUST be populated.
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
_SAME_LOCATION_METERS = 1000.0


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
        details = event.get(field) or {}
        return _latlng(details.get(o_key)), _latlng(details.get(d_key))
    if et in _SINGLE_LOC_FIELDS:
        field, key = _SINGLE_LOC_FIELDS[et]
        details = event.get(field) or {}
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


def _validate_placement(
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


def validate_itinerary_event(
    args: Dict[str, Any],
    mode: str = "autonomous",
    is_resuming: bool = False,
    prior_events: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate and coerce an add_itinerary_event call.

    Returns:
        (None, coerced_args)  on success
        (error_str, None)     on failure
    """
    event_type = args.get("event_type", "")

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

    expected_field = EVENT_TYPE_TO_DETAIL_FIELD.get(event_type)
    if not expected_field:
        log.warning("Agent tried to emit an unknown event_type..", event_type=event_type)
        return f"Unknown event_type '{event_type}'.", None

    populated_detail_fields = [
        field
        for field in EVENT_TYPE_TO_DETAIL_FIELD.values()
        if args.get(field) is not None
    ]

    if expected_field not in populated_detail_fields:
        log.warning("Agent tried to emit an event_type with a missing detail field.", event_type=event_type)
        return (
            f"event_type='{event_type}' requires '{expected_field}' to be populated, "
            f"but it is missing or null.",
            None,
        )

    extra_fields = [f for f in populated_detail_fields if f != expected_field]
    if extra_fields:
        log.warning("Agent tried to emit an event_type with extra detail fields.", event_type=event_type)
        return (
            f"event_type='{event_type}' must have ONLY '{expected_field}' populated, "
            f"but also received: {extra_fields}.",
            None,
        )

    # Commute/placement rules — only after basic shape passes.
    placement_error = _validate_placement(args, prior_events or [])
    if placement_error:
        return placement_error, None

    try:
        validated = AddItineraryEvent(**args)
        return None, validated.model_dump()
    except Exception as exc:
        log.error("Validation failed", error=str(exc))
        return str(exc), None
