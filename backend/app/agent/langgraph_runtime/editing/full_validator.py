"""Full-itinerary validation for committed edit candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.agent.langgraph_runtime.nodes.day_validator import _validate_day_events
from app.agent.langgraph_runtime.validator import _compute_open_bookings
from app.agent.schemas.structuredOutput import AddItineraryEvent

from .event_utils import (
    BOOKING_PAIR_TYPES,
    SPECIAL_TYPES,
    canonicalize_events,
    event_by_id,
    event_fingerprint,
    is_fixed_time_event,
    is_locked,
    locked_fingerprints,
    regular_events,
)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)

    @classmethod
    def success(cls) -> "ValidationResult":
        return cls(ok=True, errors=[])

    @classmethod
    def fail(cls, errors: Iterable[str]) -> "ValidationResult":
        return cls(ok=False, errors=[str(e) for e in errors if str(e).strip()])


def _schema_errors(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for event in events:
        try:
            AddItineraryEvent(**event)
        except Exception as exc:
            label = (
                f"day {event.get('day_number')}, event {event.get('event_number')} "
                f"[{event.get('event_type')}]"
            )
            errors.append(f"Schema validation failed for {label}: {exc}")
    return errors


def _start_end_errors(events: list[dict[str, Any]]) -> list[str]:
    starts = [event for event in events if event.get("event_type") == "START"]
    ends = [event for event in events if event.get("event_type") == "END"]
    errors: list[str] = []
    if len(starts) != 1:
        errors.append(f"Itinerary must contain exactly one START event; found {len(starts)}.")
    if len(ends) != 1:
        errors.append(f"Itinerary must contain exactly one END event; found {len(ends)}.")
    return errors


def _identity_errors(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_legacy: set[tuple[int, int]] = set()
    for event in events:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"Event missing event_id: {event.get('event_type')} {event.get('day_number')}/{event.get('event_number')}.")
        elif event_id in seen_ids:
            errors.append(f"Duplicate event_id {event_id}.")
        else:
            seen_ids.add(event_id)

        if event.get("event_type") in SPECIAL_TYPES:
            continue
        day = event.get("day_number")
        num = event.get("event_number")
        if not isinstance(day, int) or day <= 0:
            errors.append(f"Regular event has invalid day_number={day!r}.")
        if not isinstance(num, int) or num <= 0:
            errors.append(f"Regular event has invalid event_number={num!r}.")
        key = (day, num)
        if isinstance(day, int) and isinstance(num, int):
            if key in seen_legacy:
                errors.append(f"Duplicate legacy event reference day {day}, event {num}.")
            seen_legacy.add(key)
        if not isinstance(event.get("event_sort_key"), (int, float)):
            errors.append(f"Event day {day}, event {num} is missing event_sort_key.")
    return errors


def _pairing_errors(events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    open_items = _compute_open_bookings(events)
    for item in open_items:
        label = item.get("label") or item.get("open_event_type")
        errors.append(
            f"Open booking remains unpaired: {item.get('open_event_type')} {label} "
            f"from day {item.get('opening_day_number')}, event {item.get('opening_event_number')} "
            f"needs {item.get('must_be_closed_by')}."
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        if event.get("event_type") not in BOOKING_PAIR_TYPES:
            continue
        group_id = event.get("event_group_id")
        if not group_id:
            errors.append(
                f"Booking event day {event.get('day_number')}, event {event.get('event_number')} "
                f"[{event.get('event_type')}] is missing event_group_id."
            )
            continue
        grouped.setdefault(str(group_id), []).append(event)

    expected_pairs = {
        "hotel_stay": {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"},
        "car_rental": {"CAR_PICKUP", "CAR_DROPOFF"},
        "flight_segment": {"FLIGHT_TAKEOFF", "FLIGHT_LAND"},
    }
    for group_id, members in grouped.items():
        group_type = members[0].get("event_group_type")
        expected = expected_pairs.get(str(group_type))
        if not expected:
            continue
        got = {event.get("event_type") for event in members}
        if not expected.issubset(got):
            errors.append(
                f"Booking group {group_id} ({group_type}) is stranded; expected {sorted(expected)}, got {sorted(got)}."
            )
    return errors


def _locked_errors(base_events: list[dict[str, Any]], candidate_events: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    base_locked = locked_fingerprints(base_events)
    candidate_locked = locked_fingerprints(candidate_events)
    for event_id, fingerprint in base_locked.items():
        candidate = event_by_id(candidate_events, event_id)
        if candidate is None:
            errors.append(f"Locked event {event_id} was removed.")
            continue
        if not is_locked(candidate):
            errors.append(f"Locked event {event_id} had is_locked changed.")
            continue
        if candidate_locked.get(event_id) != fingerprint:
            errors.append(f"Locked event {event_id} was modified.")
    return errors


def _fixed_time_errors(
    base_events: list[dict[str, Any]],
    candidate_events: list[dict[str, Any]],
    allowed_fixed_event_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    for base in base_events:
        event_id = base.get("event_id")
        if not isinstance(event_id, str):
            continue
        if event_id in allowed_fixed_event_ids:
            continue
        if not is_fixed_time_event(base):
            continue
        candidate = event_by_id(candidate_events, event_id)
        if candidate is None:
            errors.append(f"Fixed-time event {event_id} was removed without being a target.")
            continue
        if event_fingerprint(base) != event_fingerprint(candidate):
            errors.append(f"Fixed-time event {event_id} changed without being a target.")
    return errors


def _day_validation_errors(
    events: list[dict[str, Any]],
    *,
    day_numbers_filter: Optional[set[int]] = None,
    smart_anchors: Optional[list[dict[str, Any]]] = None,
    locked_routines: Optional[list[dict[str, Any]]] = None,
    trip_start: Optional[dict[str, Any]] = None,
) -> list[str]:
    errors: list[str] = []
    day_numbers = sorted({
        event.get("day_number")
        for event in events
        if isinstance(event.get("day_number"), int) and event.get("day_number") > 0
    })
    if day_numbers_filter is not None:
        day_numbers = [day for day in day_numbers if day in day_numbers_filter]
    for day_number in day_numbers:
        day_events = regular_events(events, day_number)
        prior = [event for event in events if event.get("day_number") != day_number]
        day_errors = _validate_day_events(
            day_events,
            day_number,
            prior,
            smart_anchors=smart_anchors,
            locked_routines=locked_routines,
            trip_start=trip_start,
        )
        # Editing preserves locked legacy event_number values and uses
        # event_sort_key/display ordinals for order. Gaps are therefore valid
        # after insertions/removals; duplicate legacy refs are still blocked by
        # _identity_errors above.
        day_errors = [
            err for err in day_errors
            if not err.startswith("Missing event_number(s)")
        ]
        errors.extend(f"Day {day_number}: {err}" for err in day_errors)
    return errors


def validate_candidate(
    *,
    base_events: list[dict[str, Any]],
    candidate_events: list[dict[str, Any]],
    changed_event_ids: Optional[set[str]] = None,
    changed_day_numbers: Optional[set[int]] = None,
    allowed_fixed_event_ids: Optional[set[str]] = None,
    smart_anchors: Optional[list[dict[str, Any]]] = None,
    locked_routines: Optional[list[dict[str, Any]]] = None,
    trip_start: Optional[dict[str, Any]] = None,
) -> ValidationResult:
    """Validate a full candidate itinerary before snapshot/commit."""
    base = canonicalize_events(base_events)
    candidate = canonicalize_events(candidate_events)
    errors: list[str] = []

    errors.extend(_start_end_errors(candidate))
    errors.extend(_identity_errors(candidate))
    errors.extend(_schema_errors(candidate))
    errors.extend(_pairing_errors(candidate))
    errors.extend(_locked_errors(base, candidate))
    errors.extend(
        _fixed_time_errors(
            base,
            candidate,
            allowed_fixed_event_ids or changed_event_ids or set(),
        )
    )
    errors.extend(
        _day_validation_errors(
            candidate,
            day_numbers_filter=changed_day_numbers,
            smart_anchors=smart_anchors,
            locked_routines=locked_routines,
            trip_start=trip_start,
        )
    )

    if errors:
        return ValidationResult.fail(errors)
    return ValidationResult.success()
