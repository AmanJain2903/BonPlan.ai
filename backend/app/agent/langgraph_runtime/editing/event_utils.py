"""Shared event utilities for itinerary editing.

The generated itinerary schema is JSON-first and historically used
``(day_number, event_number)`` as identity. Editing needs insertions and moves
without renumbering locked rows, so this module adds stable JSON metadata while
keeping the legacy fields intact.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional

from app.agent.langgraph_runtime.validator import (
    _event_coords,
    _event_end_dt,
    _event_start_dt,
    _same_location,
)


START_SORT_KEY = -1_000_000.0
END_SORT_KEY = 1_000_000_000.0
SORT_STEP = 1000.0

DETAIL_FIELD_BY_TYPE: dict[str, str] = {
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

ANCHOR_DETAIL_FIELD_BY_TYPE: dict[str, str] = {
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

TIME_KEYS_BY_TYPE: dict[str, tuple[str, str, str]] = {
    "FLIGHT_TAKEOFF": ("flight_takeoff_details", "departure_time", "arrival_time"),
    "FLIGHT_LAND": ("flight_land_details", "arrival_time", "arrival_time"),
    "HOTEL_CHECKIN": ("hotel_checkin_details", "checkin_time", "checkin_time"),
    "HOTEL_CHECKOUT": ("hotel_checkout_details", "checkout_time", "checkout_time"),
    "CAR_PICKUP": ("car_pickup_details", "pickup_time", "pickup_time"),
    "CAR_DROPOFF": ("car_dropoff_details", "dropoff_time", "dropoff_time"),
    "DINING": ("place_details", "start_time", "end_time"),
    "ACTIVITY": ("place_details", "start_time", "end_time"),
    "OTHER": ("other_details", "start_time", "end_time"),
}

FLEXIBLE_TIMED_TYPES = {"DINING", "ACTIVITY", "OTHER"}
BOOKING_PAIR_TYPES = {
    "HOTEL_CHECKIN",
    "HOTEL_CHECKOUT",
    "CAR_PICKUP",
    "CAR_DROPOFF",
    "FLIGHT_TAKEOFF",
    "FLIGHT_LAND",
}
FIXED_TIME_TYPES = BOOKING_PAIR_TYPES
SPECIAL_TYPES = {"START", "END"}

SYSTEM_METADATA_KEYS = {
    "event_id",
    "event_sort_key",
    "event_group_id",
    "event_group_type",
    "display_event_number",
    "_updatedAt",
}


def clone_events(events: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return copy.deepcopy(list(events or []))


def detail_field_for_event(event: dict[str, Any]) -> Optional[str]:
    event_type = event.get("event_type")
    field = DETAIL_FIELD_BY_TYPE.get(event_type)
    if field and isinstance(event.get(field), dict):
        return field
    anchor_field = ANCHOR_DETAIL_FIELD_BY_TYPE.get(event_type)
    if anchor_field and isinstance(event.get(anchor_field), dict):
        return anchor_field
    return field


def event_details(event: dict[str, Any]) -> dict[str, Any]:
    field = detail_field_for_event(event)
    if not field:
        return {}
    details = event.get(field) or {}
    return details if isinstance(details, dict) else {}


def event_name(event: dict[str, Any]) -> str:
    event_type = event.get("event_type") or ""
    details = event_details(event)
    for key in (
        "event_name",
        "place_name",
        "hotel_name",
        "flight_number",
        "rental_company_name",
        "originName",
        "destinationName",
        "trip_title",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            if key == "flight_number":
                airline = details.get("airline")
                return f"{airline} {value}".strip() if airline else value.strip()
            return value.strip()
    if event_type == "COMMUTE":
        origin = details.get("originName") or "origin"
        dest = details.get("destinationName") or "destination"
        return f"Commute from {origin} to {dest}"
    return event_type.replace("_", " ").title() if event_type else "Event"


def event_description(event: dict[str, Any]) -> str:
    details = event_details(event)
    for key in (
        "event_description",
        "summary",
        "event_tips",
        "takeoff_tips",
        "landing_tips",
        "checkin_tips",
        "checkout_tips",
        "pickup_tips",
        "dropoff_tips",
        "commute_tips",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def event_location_name(event: dict[str, Any]) -> str:
    details = event_details(event)
    for key in (
        "place_name",
        "hotel_name",
        "address",
        "pickup_location_name",
        "dropoff_location_name",
        "departure_airport_name",
        "arrival_airport_name",
        "originName",
        "destinationName",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return event_name(event)


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for prefix in ("the ", "a ", "an "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text


def parse_dt(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def event_start(event: dict[str, Any]) -> Optional[datetime]:
    return _event_start_dt(event) or parse_dt(event_details(event).get("start_time"))


def event_end(event: dict[str, Any]) -> Optional[datetime]:
    return _event_end_dt(event) or event_start(event)


def event_duration_minutes(event: dict[str, Any], default: int = 60) -> int:
    details = event_details(event)
    value = details.get("durationMinutes")
    try:
        if value is not None:
            return max(5, int(round(float(value))))
    except (TypeError, ValueError):
        pass
    start = event_start(event)
    end = event_end(event)
    if start and end and end >= start:
        return max(5, int(round((end - start).total_seconds() / 60)))
    return default


def is_timed_event(event: dict[str, Any]) -> bool:
    return event_start(event) is not None or event.get("event_type") in TIME_KEYS_BY_TYPE


def is_flexible_timed_event(event: dict[str, Any]) -> bool:
    return event.get("event_type") in FLEXIBLE_TIMED_TYPES


def is_fixed_time_event(event: dict[str, Any]) -> bool:
    return event.get("event_type") in FIXED_TIME_TYPES


def is_locked(event: dict[str, Any]) -> bool:
    return event.get("is_locked") is True


def set_event_window(event: dict[str, Any], start: datetime, end: datetime) -> dict[str, Any]:
    """Set start/end on an event that has editable event-window fields."""
    result = copy.deepcopy(event)
    event_type = result.get("event_type")
    if event_type not in TIME_KEYS_BY_TYPE:
        return result
    field, start_key, end_key = TIME_KEYS_BY_TYPE[event_type]
    details = dict(result.get(field) or {})
    details[start_key] = format_dt(start)
    details[end_key] = format_dt(end)
    if "durationMinutes" in details or event_type in FLEXIBLE_TIMED_TYPES:
        details["durationMinutes"] = max(5, int(round((end - start).total_seconds() / 60)))
    result[field] = details
    result["date"] = start.date().isoformat()
    return result


def shift_event_time(event: dict[str, Any], delta: timedelta) -> dict[str, Any]:
    start = event_start(event)
    end = event_end(event)
    if start is None or end is None:
        return copy.deepcopy(event)
    return set_event_window(event, start + delta, end + delta)


def event_origin_dest(event: dict[str, Any]):
    return _event_coords(event)


def events_same_location(left: dict[str, Any], right: dict[str, Any]) -> bool:
    _, left_dest = event_origin_dest(left)
    right_origin, _ = event_origin_dest(right)
    return _same_location(left_dest, right_origin)


def trip_start_date(trip_input: dict[str, Any]) -> Optional[date]:
    start = trip_input.get("start_date") or {}
    try:
        return date(int(start["year"]), int(start["month"]), int(start["day"]))
    except Exception:
        return None


def date_for_day(trip_input: dict[str, Any], day_number: int) -> str:
    base = trip_start_date(trip_input)
    if base is None or day_number <= 0:
        return ""
    return (base + timedelta(days=day_number - 1)).isoformat()


def day_title(day_number: int, existing_events: Iterable[dict[str, Any]] | None = None) -> str:
    for event in existing_events or []:
        if event.get("day_number") == day_number and isinstance(event.get("day_title"), str):
            title = event.get("day_title") or ""
            if title.strip():
                return title
    return f"Day {day_number}"


def day_sort_key(event: dict[str, Any]) -> tuple[int, float, int]:
    event_type = event.get("event_type")
    if event_type == "START":
        return (0, START_SORT_KEY, 0)
    if event_type == "END":
        return (10_000_000, END_SORT_KEY, 0)
    day = event.get("day_number")
    if not isinstance(day, int):
        day = 999_999
    raw_sort = event.get("event_sort_key")
    try:
        sort_key = float(raw_sort)
    except (TypeError, ValueError):
        sort_key = float(event.get("event_number") or 0) * SORT_STEP
    event_number = event.get("event_number") if isinstance(event.get("event_number"), int) else 0
    return (day, sort_key, event_number)


def regular_events(events: Iterable[dict[str, Any]], day_number: Optional[int] = None) -> list[dict[str, Any]]:
    out = [
        e for e in events
        if isinstance(e, dict) and e.get("event_type") not in SPECIAL_TYPES
    ]
    if day_number is not None:
        out = [e for e in out if e.get("day_number") == day_number]
    return sorted(out, key=day_sort_key)


def next_legacy_event_number(events: Iterable[dict[str, Any]], day_number: int) -> int:
    current = [
        e.get("event_number")
        for e in events
        if e.get("day_number") == day_number and isinstance(e.get("event_number"), int)
    ]
    return (max(current) + 1) if current else 1


def sort_key_between(before: Optional[dict[str, Any]], after: Optional[dict[str, Any]], fallback: float) -> float:
    if before is not None:
        try:
            before_key = float(before.get("event_sort_key"))
        except (TypeError, ValueError):
            before_key = float(before.get("event_number") or 0) * SORT_STEP
    else:
        before_key = None

    if after is not None:
        try:
            after_key = float(after.get("event_sort_key"))
        except (TypeError, ValueError):
            after_key = float(after.get("event_number") or 0) * SORT_STEP
    else:
        after_key = None

    if before_key is not None and after_key is not None and after_key > before_key:
        return before_key + (after_key - before_key) / 2.0
    if before_key is not None:
        return before_key + SORT_STEP
    if after_key is not None:
        return after_key - SORT_STEP if after_key > SORT_STEP else after_key / 2.0
    return fallback


def _event_group_label(event: dict[str, Any]) -> str:
    event_type = event.get("event_type")
    details = event_details(event)
    if event_type in {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"}:
        return normalize_text(details.get("hotel_name")) or "hotel"
    if event_type in {"CAR_PICKUP", "CAR_DROPOFF"}:
        return normalize_text(details.get("rental_company_name")) or "car"
    if event_type in {"FLIGHT_TAKEOFF", "FLIGHT_LAND"}:
        # Flight generation can have different leg numbers and sparse anchor
        # fields; pair by chronological opener/closer sequence.
        return "flight"
    return ""


def _event_group_type(event_type: Any) -> Optional[str]:
    if event_type in {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"}:
        return "hotel_stay"
    if event_type in {"CAR_PICKUP", "CAR_DROPOFF"}:
        return "car_rental"
    if event_type in {"FLIGHT_TAKEOFF", "FLIGHT_LAND"}:
        return "flight_segment"
    return None


def ensure_event_identities(events: Iterable[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], bool]:
    """Backfill stable JSON identity/order metadata and paired-group ids."""
    result = clone_events(events)
    changed = False
    seen_ids: set[str] = set()

    for index, event in enumerate(result):
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip() or event_id in seen_ids:
            stable_payload = {
                key: value
                for key, value in event.items()
                if key not in SYSTEM_METADATA_KEYS
            }
            stable_payload["_legacy_index"] = index
            stable = hashlib.sha256(canonical_json(stable_payload).encode("utf-8")).hexdigest()[:32]
            candidate_id = f"evt_{stable}"
            suffix = 1
            while candidate_id in seen_ids:
                suffix += 1
                candidate_id = f"evt_{stable}_{suffix}"
            event["event_id"] = candidate_id
            changed = True
        seen_ids.add(event["event_id"])

        if event.get("event_type") == "START":
            if event.get("event_sort_key") != START_SORT_KEY:
                event["event_sort_key"] = START_SORT_KEY
                changed = True
            continue
        if event.get("event_type") == "END":
            if event.get("event_sort_key") != END_SORT_KEY:
                event["event_sort_key"] = END_SORT_KEY
                changed = True
            continue

        if not isinstance(event.get("day_number"), int):
            event["day_number"] = 1
            changed = True
        if not isinstance(event.get("event_number"), int) or event.get("event_number") < 1:
            event["event_number"] = index + 1
            changed = True
        if not isinstance(event.get("event_sort_key"), (int, float)):
            event["event_sort_key"] = float(event.get("event_number") or index + 1) * SORT_STEP
            changed = True

    changed = _ensure_group_ids_in_place(result) or changed
    return canonicalize_events(result), changed


def _ensure_group_ids_in_place(events: list[dict[str, Any]]) -> bool:
    changed = False
    openers: dict[tuple[str, str], list[dict[str, Any]]] = {}
    sorted_events = sorted(events, key=day_sort_key)

    opener_types = {"HOTEL_CHECKIN", "CAR_PICKUP", "FLIGHT_TAKEOFF"}
    closer_types = {"HOTEL_CHECKOUT", "CAR_DROPOFF", "FLIGHT_LAND"}

    for event in sorted_events:
        event_type = event.get("event_type")
        group_type = _event_group_type(event_type)
        if group_type is None:
            continue
        label = _event_group_label(event)
        key = (group_type, label)
        if event_type in opener_types:
            openers.setdefault(key, []).append(event)
            continue
        if event_type not in closer_types:
            continue
        candidates = openers.get(key) or []
        if not candidates and group_type == "flight_segment":
            candidates = openers.get((group_type, "flight")) or []
        opener = candidates.pop(0) if candidates else None
        existing_group = (
            event.get("event_group_id")
            or (opener or {}).get("event_group_id")
        )
        if not existing_group:
            seed = f"{group_type}:{label}:{(opener or {}).get('event_id')}:{event.get('event_id')}"
            existing_group = f"grp_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:32]}"
        for member in (opener, event):
            if not member:
                continue
            if member.get("event_group_id") != existing_group:
                member["event_group_id"] = existing_group
                changed = True
            if member.get("event_group_type") != group_type:
                member["event_group_type"] = group_type
                changed = True

    return changed


def canonicalize_events(
    events: Iterable[dict[str, Any]] | None,
    *,
    include_display_numbers: bool = False,
) -> list[dict[str, Any]]:
    ordered = clone_events(events)
    ordered.sort(key=day_sort_key)
    if not include_display_numbers:
        for event in ordered:
            event.pop("display_event_number", None)
        return ordered

    counters: dict[int, int] = {}
    for event in ordered:
        if event.get("event_type") in SPECIAL_TYPES:
            event["display_event_number"] = event.get("event_number")
            continue
        day = event.get("day_number")
        if not isinstance(day, int):
            continue
        counters[day] = counters.get(day, 0) + 1
        event["display_event_number"] = counters[day]
    return ordered


def events_hash(events: Iterable[dict[str, Any]] | None) -> str:
    payload = canonical_json(canonicalize_events(events))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def event_fingerprint(event: dict[str, Any], *, include_system_metadata: bool = True) -> str:
    value = copy.deepcopy(event)
    value.pop("display_event_number", None)
    value.pop("_updatedAt", None)
    if not include_system_metadata:
        for key in SYSTEM_METADATA_KEYS:
            value.pop(key, None)
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def locked_fingerprints(events: Iterable[dict[str, Any]] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for event in events or []:
        if isinstance(event, dict) and is_locked(event):
            event_id = event.get("event_id")
            if isinstance(event_id, str):
                out[event_id] = event_fingerprint(event)
    return out


def group_members(events: Iterable[dict[str, Any]], event: dict[str, Any]) -> list[dict[str, Any]]:
    group_id = event.get("event_group_id")
    if not group_id:
        return [event]
    members = [
        candidate for candidate in events
        if isinstance(candidate, dict) and candidate.get("event_group_id") == group_id
    ]
    return sorted(members, key=day_sort_key) or [event]


def event_by_id(events: Iterable[dict[str, Any]], event_id: str) -> Optional[dict[str, Any]]:
    for event in events:
        if isinstance(event, dict) and event.get("event_id") == event_id:
            return event
    return None


def event_by_legacy_ref(
    events: Iterable[dict[str, Any]],
    day_number: int,
    event_number: int,
) -> Optional[dict[str, Any]]:
    for event in events:
        if (
            isinstance(event, dict)
            and event.get("day_number") == day_number
            and event.get("event_number") == event_number
        ):
            return event
    return None


def replace_event_by_id(
    events: Iterable[dict[str, Any]],
    event_id: str,
    replacement: dict[str, Any],
) -> list[dict[str, Any]]:
    out = []
    replaced = False
    for event in events:
        if isinstance(event, dict) and event.get("event_id") == event_id:
            out.append(copy.deepcopy(replacement))
            replaced = True
        else:
            out.append(copy.deepcopy(event))
    if not replaced:
        out.append(copy.deepcopy(replacement))
    return canonicalize_events(out)


def remove_event_ids(events: Iterable[dict[str, Any]], event_ids: set[str]) -> list[dict[str, Any]]:
    return canonicalize_events([
        event for event in clone_events(events)
        if event.get("event_id") not in event_ids
    ])


def compact_event_for_prompt(event: dict[str, Any]) -> dict[str, Any]:
    start = event_start(event)
    end = event_end(event)
    return {
        "event_id": event.get("event_id"),
        "day_number": event.get("day_number"),
        "event_number": event.get("event_number"),
        "event_sort_key": event.get("event_sort_key"),
        "event_group_id": event.get("event_group_id"),
        "event_group_type": event.get("event_group_type"),
        "event_type": event.get("event_type"),
        "is_locked": event.get("is_locked") is True,
        "name": event_name(event),
        "description": event_description(event)[:220],
        "date": event.get("date"),
        "start_time": format_dt(start) if start else None,
        "end_time": format_dt(end) if end else None,
    }


def compact_itinerary_for_prompt(events: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [compact_event_for_prompt(event) for event in canonicalize_events(events)]


def day_boundaries(events: Iterable[dict[str, Any]], day_number: int) -> list[dict[str, Any]]:
    return regular_events(events, day_number)


def finite_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default
