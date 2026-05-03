"""Aggregate billable USD amounts from persisted itinerary events (JSON rows)."""

from __future__ import annotations

from typing import Any

# (details_field, cost_key) for each event shape that contributes to trip total.
_CHARGE_SOURCES: tuple[tuple[str, str], ...] = (
    ("flight_takeoff_details", "cost"),
    ("hotel_checkin_details", "cost"),
    ("car_pickup_details", "cost"),
    ("place_details", "cost"),
    ("other_details", "cost"),
    ("commute_details", "transit_fare"),
)


def sum_chargeable_cost_usd(events: list[Any] | None) -> float:
    """Mirror frontend `getEventCost` / finalizer rollup: excludes START and END."""
    total = 0.0
    for e in events or []:
        if not isinstance(e, dict):
            continue
        for field, key in _CHARGE_SOURCES:
            details = e.get(field) or {}
            if not isinstance(details, dict):
                continue
            val = details.get(key)
            try:
                if val is not None:
                    total += float(val)
            except (TypeError, ValueError):
                continue
    return round(total, 2)
