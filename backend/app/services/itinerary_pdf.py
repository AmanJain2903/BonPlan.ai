"""PDF rendering helpers for generated trip itineraries."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent
TEMPLATE_DIR = APP_DIR / "templates"
TEMPLATE_NAME = "itinerary_pdf.html"

EVENT_DETAIL_FIELDS = {
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
}

EVENT_LABELS = {
    "FLIGHT_TAKEOFF": "Flight Departure",
    "FLIGHT_LAND": "Flight Arrival",
    "HOTEL_CHECKIN": "Hotel Check-in",
    "HOTEL_CHECKOUT": "Hotel Check-out",
    "CAR_PICKUP": "Rental Car Pickup",
    "CAR_DROPOFF": "Rental Car Drop-off",
    "DINING": "Dining",
    "ACTIVITY": "Activity",
    "COMMUTE": "Transfer",
    "OTHER": "Planner Note",
}

EVENT_ACCENTS = {
    "FLIGHT_TAKEOFF": "#2563eb",
    "FLIGHT_LAND": "#2563eb",
    "HOTEL_CHECKIN": "#7c3aed",
    "HOTEL_CHECKOUT": "#7c3aed",
    "CAR_PICKUP": "#0f766e",
    "CAR_DROPOFF": "#0f766e",
    "DINING": "#b45309",
    "ACTIVITY": "#0891b2",
    "COMMUTE": "#475569",
    "OTHER": "#334155",
}

KEY_LABELS = {
    "nbRooms": "Rooms",
    "nbAdults": "Adults",
    "nbChildren": "Children",
    "stayLengthInDays": "Stay length",
    "starRating": "Hotel stars",
    "durationMinutes": "Duration",
    "durationSeconds": "Duration",
    "distanceMeters": "Distance",
    "transit_fare": "Transit fare",
    "free_cancellation": "Free cancellation",
    "pickup_instructions": "Pickup instructions",
    "dropoff_instructions": "Drop-off instructions",
    "checkin_rules": "Check-in rules",
    "checkout_rules": "Check-out rules",
    "reviews_summary": "Review summary",
    "travel_mode": "Travel mode",
}

DETAIL_SKIP_KEYS = {
    "airline_logo_url",
    "rental_company_logo_url",
    "logo_url",
    "booking_url",
    "google_maps_url",
    "maps_url",
    "website_url",
    "place_id",
    "hotel_id",
    "vehicle_id",
    "coordinates",
    "departure_coordinates",
    "arrival_coordinates",
    "hotel_coordinates",
    "pickup_location_coordinates",
    "dropoff_location_coordinates",
    "origin_coordinates",
    "destination_coordinates",
    "event_description",
    "event_tips",
    "summary",
    "takeoff_tips",
    "landing_tips",
    "checkin_tips",
    "checkout_tips",
    "pickup_tips",
    "dropoff_tips",
    "commute_tips",
    "cost",
    "transit_fare",
    "start_time",
    "end_time",
    "departure_time",
    "arrival_time",
    "checkin_time",
    "checkout_time",
    "pickup_time",
    "dropoff_time",
}

URL_LABELS = {
    "booking_url": "Booking",
    "google_maps_url": "Google Maps",
    "maps_url": "Route",
    "website_url": "Website",
}


def build_itinerary_pdf(plan: Any, itinerary: Any, generated_for: Any | None = None) -> bytes:
    """Render a generated itinerary row to PDF bytes."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from weasyprint import HTML

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_NAME)
    html = template.render(**build_itinerary_pdf_context(plan, itinerary, generated_for))
    return HTML(string=html, base_url=str(PROJECT_ROOT)).write_pdf()


def itinerary_pdf_filename(title: str | None, trip_id: Any) -> str:
    base = title or f"itinerary-{trip_id}"
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", str(base)).strip("-").lower()
    return f"{base or 'bonplan-itinerary'}.pdf"


def build_itinerary_pdf_context(plan: Any, itinerary: Any, generated_for: Any | None = None) -> dict[str, Any]:
    events = _coerce_list(_attr(itinerary, "events")) or []
    title = _first_text(
        _attr(itinerary, "title"),
        _start_detail(events, "trip_title"),
        _end_detail(events, "trip_title"),
        "BonPlan itinerary",
    )
    destinations = _destination_names(_attr(itinerary, "destinations")) or _destination_names(_attr(plan, "destinations"))
    origin = _first_text(_attr(itinerary, "origin"), _location_name(_attr(plan, "origin")), "Origin")
    route_label = _journey_label(origin, destinations)
    start_date = _attr(itinerary, "start_date") or _attr(plan, "start_date")
    end_date = _attr(itinerary, "end_date") or _attr(plan, "end_date")
    days = _build_days(events, int(_attr(itinerary, "days") or 0))
    day_overviews = _build_day_overviews(days)
    generated_at = _attr(itinerary, "updated_at") or datetime.now(timezone.utc)
    trip_cost = _number_or_none(_attr(itinerary, "cost"))
    if trip_cost is None:
        trip_cost = round(sum(day["cost_value"] for day in days), 2)

    adults = int(_attr(plan, "adults") or 0)
    children = int(_attr(plan, "children") or 0)
    travelers = _traveler_label(adults, children)
    generated_for_name = _user_display_name(generated_for)
    owner_name = _user_display_name(_attr(plan, "owner"))
    logo_data_uri = _logo_data_uri()
    trip_tips = _coerce_tips(_attr(itinerary, "tips")) or _coerce_tips(_end_detail(events, "trip_tips"))

    summary_cards = [
        {"label": "Dates", "value": _date_range_label(start_date, end_date)},
        {"label": "Travelers", "value": travelers},
        {"label": "Estimated Cost", "value": _format_money(trip_cost)},
        {"label": "Trip Length", "value": _days_label(_attr(itinerary, "days"), days)},
        {"label": "Pace", "value": _first_text(_attr(plan, "pace"), "Not specified")},
        {"label": "Budget", "value": _first_text(_attr(plan, "budget"), "Not specified")},
    ]

    trip_details = [
        {"label": "Journey Path", "value": route_label},
        {"label": "Origin", "value": origin},
        {"label": "Destinations", "value": ", ".join(destinations) if destinations else "Not specified"},
        {"label": "Planning Type", "value": _titleize(_enum_value(_attr(plan, "planning_type")))},
        {"label": "Routing Style", "value": _titleize(_enum_value(_attr(plan, "routing_style")))},
        {"label": "Generated For", "value": generated_for_name or "Traveler"},
        {"label": "Owner", "value": owner_name or "Not specified"},
        {"label": "Prepared On", "value": _format_datetime(generated_at)},
    ]

    return {
        "app_name": "BonPlan.ai",
        "logo_data_uri": logo_data_uri,
        "title": title,
        "route_label": route_label,
        "date_range": _date_range_label(start_date, end_date),
        "generated_on": _format_datetime(generated_at),
        "prepared_for": generated_for_name,
        "summary_cards": summary_cards,
        "trip_details": trip_details,
        "day_overviews": day_overviews,
        "trip_tips": trip_tips,
        "days": days,
        "total_events": sum(len(day["events"]) for day in days),
        "total_cost": _format_money(trip_cost),
        "has_logo": bool(logo_data_uri),
    }


def _build_days(events: list[Any], configured_days: int) -> list[dict[str, Any]]:
    regular_events = _dedupe_regular_events(events)
    max_day = max([configured_days] + [int(e.get("day_number") or 0) for e in regular_events] + [0])
    days: list[dict[str, Any]] = []

    for day_number in range(1, max_day + 1):
        day_events_raw = [e for e in regular_events if e.get("day_number") == day_number]
        normalized_events = [_normalize_event(e) for e in day_events_raw]
        normalized_events = [event for event in normalized_events if event is not None]
        day_title = _first_text(
            *(e.get("day_title") for e in day_events_raw),
            f"Day {day_number}",
        )
        day_date = _first_text(*(e.get("date") for e in day_events_raw), "")
        cost_value = round(sum(event["cost_value"] or 0 for event in normalized_events), 2)
        days.append(
            {
                "day_number": day_number,
                "title": _clean_day_title(day_title, day_number),
                "date_label": _format_date(day_date) if day_date else "",
                "events": normalized_events,
                "event_count": len(normalized_events),
                "scheduled_count": sum(1 for event in normalized_events if event["event_type"] != "COMMUTE"),
                "transfer_count": sum(1 for event in normalized_events if event["event_type"] == "COMMUTE"),
                "cost_value": cost_value,
                "cost": _format_money(cost_value),
            }
        )
    return days


def _normalize_event(event: dict[str, Any]) -> dict[str, Any] | None:
    event_type = str(event.get("event_type") or "OTHER").upper()
    detail_field = EVENT_DETAIL_FIELDS.get(event_type)
    details = event.get(detail_field) if detail_field else None
    if not isinstance(details, dict):
        details = {}

    title, subtitle = _event_title_and_subtitle(event_type, details)
    time_label = _event_time_label(event_type, details)
    duration_label = _event_duration_label(event_type, details)
    distance_label = _event_distance_label(details)
    cost_value = _event_cost_value(event_type, details)
    rating_label = _rating_label(details)
    location = _event_location(event_type, details)
    descriptions = _event_descriptions(details)
    tips = _event_tips(event_type, details)
    links = _event_links(details)
    detail_rows = _detail_rows(details)

    badges = []
    for label, value in (
        ("Time", time_label),
        ("Duration", duration_label),
        ("Distance", distance_label),
        ("Cost", _format_money(cost_value) if cost_value is not None else None),
        ("Rating", rating_label),
    ):
        if value:
            badges.append({"label": label, "value": value})

    accent_hex = EVENT_ACCENTS.get(event_type, "#334155")
    return {
        "event_type": event_type,
        "label": EVENT_LABELS.get(event_type, _titleize(event_type)),
        "accent": accent_hex,
        # Full attribute fragment so the HTML template avoids Jinja inside `style="..."` (CSS parser error).
        "accent_attr": f' style="background:{accent_hex}"',
        "event_number": event.get("event_number"),
        "title": title,
        "subtitle": subtitle,
        "time_label": time_label,
        "duration_label": duration_label,
        "cost_value": cost_value or 0,
        "cost": _format_money(cost_value) if cost_value is not None else "",
        "location": location,
        "descriptions": descriptions,
        "tips": tips,
        "links": links,
        "details": detail_rows,
        "badges": badges,
    }


def _event_title_and_subtitle(event_type: str, details: dict[str, Any]) -> tuple[str, str]:
    if event_type == "FLIGHT_TAKEOFF":
        airline = _first_text(details.get("airline"), "Flight")
        flight = _first_text(details.get("flight_number"), "")
        route = _airport_route(details)
        return f"{airline} {flight}".strip(), route
    if event_type == "FLIGHT_LAND":
        return _first_text(details.get("arrival_airport_name"), "Flight arrival"), _first_text(details.get("arrival_airport_code"), "")
    if event_type == "HOTEL_CHECKIN":
        return f"Check in at {_first_text(details.get('hotel_name'), 'hotel')}", _first_text(details.get("address"), "")
    if event_type == "HOTEL_CHECKOUT":
        return f"Check out from {_first_text(details.get('hotel_name'), 'hotel')}", _first_text(details.get("address"), "")
    if event_type == "CAR_PICKUP":
        vehicle = _vehicle_name(details.get("vehicle"))
        return f"Pick up {_first_text(vehicle, 'rental car')}", _first_text(details.get("rental_company_name"), details.get("pickup_location_name"), "")
    if event_type == "CAR_DROPOFF":
        return "Return rental car", _first_text(details.get("rental_company_name"), details.get("dropoff_location_name"), "")
    if event_type in {"DINING", "ACTIVITY"}:
        return _first_text(details.get("event_name"), details.get("place_name"), EVENT_LABELS[event_type]), _first_text(details.get("place_name"), "")
    if event_type == "COMMUTE":
        return f"Transfer to {_first_text(details.get('destinationName'), 'next stop')}", _first_text(details.get("originName"), "")
    if event_type == "OTHER":
        return _first_text(details.get("event_name"), details.get("place_name"), "Planner note"), _first_text(details.get("place_name"), "")
    return _titleize(event_type), ""


def _event_time_label(event_type: str, details: dict[str, Any]) -> str:
    pairs = {
        "FLIGHT_TAKEOFF": ("departure_time", "arrival_time"),
        "FLIGHT_LAND": ("arrival_time", None),
        "HOTEL_CHECKIN": ("checkin_time", None),
        "HOTEL_CHECKOUT": ("checkout_time", None),
        "CAR_PICKUP": ("pickup_time", None),
        "CAR_DROPOFF": ("dropoff_time", None),
        "DINING": ("start_time", "end_time"),
        "ACTIVITY": ("start_time", "end_time"),
        "OTHER": ("start_time", "end_time"),
    }
    start_key, end_key = pairs.get(event_type, (None, None))
    start = _format_time(details.get(start_key)) if start_key else ""
    end = _format_time(details.get(end_key)) if end_key else ""
    if start and end and start != end:
        return f"{start} - {end}"
    return start or end


def _event_duration_label(event_type: str, details: dict[str, Any]) -> str:
    if event_type == "COMMUTE":
        return _format_duration_seconds(details.get("durationSeconds"))
    if details.get("durationMinutes") is not None:
        return _format_duration_minutes(details.get("durationMinutes"))
    if event_type == "FLIGHT_TAKEOFF" and details.get("durationMinutes") is not None:
        return _format_duration_minutes(details.get("durationMinutes"))
    return ""


def _event_distance_label(details: dict[str, Any]) -> str:
    if details.get("distanceMeters") is None:
        return ""
    return _format_distance_meters(details.get("distanceMeters"))


def _event_cost_value(event_type: str, details: dict[str, Any]) -> float | None:
    key = "transit_fare" if event_type == "COMMUTE" else "cost"
    return _number_or_none(details.get(key))


def _event_location(event_type: str, details: dict[str, Any]) -> str:
    if event_type == "FLIGHT_TAKEOFF":
        return _first_text(details.get("departure_airport_name"), details.get("departure_airport_code"), "")
    if event_type == "FLIGHT_LAND":
        return _first_text(details.get("arrival_airport_name"), details.get("arrival_airport_code"), "")
    if event_type in {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"}:
        return _first_text(details.get("address"), details.get("hotel_name"), "")
    if event_type == "CAR_PICKUP":
        return _first_text(details.get("pickup_location_address"), details.get("pickup_location_name"), "")
    if event_type == "CAR_DROPOFF":
        return _first_text(details.get("dropoff_location_address"), details.get("dropoff_location_name"), "")
    if event_type in {"DINING", "ACTIVITY", "OTHER"}:
        return _first_text(details.get("address"), details.get("place_name"), "")
    if event_type == "COMMUTE":
        origin = _first_text(details.get("originName"), "")
        destination = _first_text(details.get("destinationName"), "")
        if origin and destination:
            return f"{origin} to {destination}"
        return origin or destination
    return ""


def _event_descriptions(details: dict[str, Any]) -> list[str]:
    values = []
    for key in ("summary", "event_description", "reviews_summary"):
        value = _clean_text(details.get(key))
        if value and value not in values:
            values.append(value)
    return values


def _event_tips(event_type: str, details: dict[str, Any]) -> list[str]:
    keys = {
        "FLIGHT_TAKEOFF": ("takeoff_tips",),
        "FLIGHT_LAND": ("landing_tips",),
        "HOTEL_CHECKIN": ("checkin_tips",),
        "HOTEL_CHECKOUT": ("checkout_tips",),
        "CAR_PICKUP": ("pickup_tips",),
        "CAR_DROPOFF": ("dropoff_tips",),
        "COMMUTE": ("commute_tips",),
        "DINING": ("event_tips",),
        "ACTIVITY": ("event_tips",),
        "OTHER": ("event_tips",),
    }.get(event_type, ("event_tips",))
    tips: list[str] = []
    for key in keys:
        tips.extend(_coerce_tips(details.get(key)))
    return tips


def _event_links(details: dict[str, Any]) -> list[dict[str, str]]:
    links = []
    seen = set()
    for key, label in URL_LABELS.items():
        url = _clean_text(details.get(key))
        if not _is_url(url) or url in seen:
            continue
        seen.add(url)
        links.append({"label": label, "url": url})
    return links


def _detail_rows(details: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for key, value in details.items():
        if key in DETAIL_SKIP_KEYS:
            continue
        formatted = _format_detail_value(value, key)
        if not formatted:
            continue
        rows.append({"label": _humanize_key(key), "value": formatted})
    return rows


def _format_detail_value(value: Any, key: str = "") -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        if key == "durationMinutes":
            return _format_duration_minutes(value)
        if key == "durationSeconds":
            return _format_duration_seconds(value)
        if key == "distanceMeters":
            return _format_distance_meters(value)
        return f"{value:g}" if isinstance(value, float) else str(value)
    if isinstance(value, str):
        text = _clean_text(value)
        if not text:
            return ""
        if key.endswith("_time") or key in {"start_time", "end_time"}:
            return _format_datetime(text)
        return text
    if isinstance(value, list):
        items = []
        for item in value:
            formatted = _format_detail_value(item)
            if formatted:
                items.append(formatted)
        return "\n".join(items)
    if isinstance(value, dict):
        if {"latitude", "longitude"}.issubset(value.keys()):
            lat = _number_or_none(value.get("latitude"))
            lng = _number_or_none(value.get("longitude"))
            if lat is not None and lng is not None:
                return f"{lat:.5f}, {lng:.5f}"
        parts = []
        for sub_key, sub_value in value.items():
            formatted = _format_detail_value(sub_value, sub_key)
            if formatted:
                parts.append(f"{_humanize_key(sub_key)}: {formatted}")
        return "\n".join(parts)
    return _clean_text(str(value))


def _dedupe_regular_events(events: list[Any]) -> list[dict[str, Any]]:
    keyed: dict[tuple[int, int], dict[str, Any]] = {}
    loose: list[dict[str, Any]] = []
    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue
        event_type = str(raw_event.get("event_type") or "").upper()
        if event_type in {"START", "END"}:
            continue
        day_number = raw_event.get("day_number")
        event_number = raw_event.get("event_number")
        if not isinstance(day_number, int) or day_number <= 0:
            continue
        if isinstance(event_number, int):
            keyed[(day_number, event_number)] = raw_event
        else:
            loose.append(raw_event)
    regular = list(keyed.values()) + loose
    return sorted(
        regular,
        key=lambda e: (
            int(e.get("day_number") or 0),
            int(e.get("event_number") or 9999) if isinstance(e.get("event_number"), int) else 9999,
        ),
    )


def _start_detail(events: list[Any], key: str) -> Any:
    for event in events:
        if isinstance(event, dict) and str(event.get("event_type") or "").upper() == "START":
            details = event.get("start_details") or {}
            if isinstance(details, dict):
                return details.get(key)
    return None


def _end_detail(events: list[Any], key: str) -> Any:
    for event in reversed(events):
        if isinstance(event, dict) and str(event.get("event_type") or "").upper() == "END":
            details = event.get("end_details") or {}
            if isinstance(details, dict):
                return details.get(key)
    return None


def _logo_data_uri() -> str:
    for path in (
        PROJECT_ROOT / "frontend" / "public" / "logo.png",
        PROJECT_ROOT / "frontend" / "dist" / "logo.png",
    ):
        if not path.exists():
            continue
        mime = mimetypes.guess_type(str(path))[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    return ""


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value.value if hasattr(value, "value") else value)


def _coerce_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _coerce_tips(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item) for item in value if _clean_text(item)]
    if isinstance(value, str):
        raw = value.strip()
        cleaned = _clean_text(raw)
        if not cleaned:
            return []
        lines = [_clean_text(line.strip(" -\t")) for line in raw.splitlines()]
        lines = [line for line in lines if line]
        return lines if len(lines) > 1 else [cleaned]
    return []


def _first_text(*values: Any) -> str:
    for value in values:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"\s+", " ", value).strip()


def _number_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, dict):
        for key in ("localTimeString", "utcTimeString", "iso"):
            if value.get(key):
                parsed = _parse_datetime(value.get(key))
                if parsed:
                    return parsed
        try:
            return datetime(
                int(value["year"]),
                int(value["month"]),
                int(value["day"]),
                int(value.get("hour", 0) or 0),
                int(value.get("minute", 0) or 0),
            )
        except Exception:
            return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"start", "end"}:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _format_date(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return _clean_text(value)
    return parsed.strftime("%b %d, %Y").replace(" 0", " ")


def _format_time(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return ""
    return parsed.strftime("%I:%M %p").lstrip("0")


def _format_datetime(value: Any) -> str:
    parsed = _parse_datetime(value)
    if not parsed:
        return _clean_text(value)
    date = parsed.strftime("%b %d, %Y").replace(" 0", " ")
    time = parsed.strftime("%I:%M %p").lstrip("0")
    return f"{date} at {time} UTC"


def _date_range_label(start: Any, end: Any) -> str:
    start_label = _format_date(start)
    end_label = _format_date(end)
    if start_label and end_label and start_label != end_label:
        return f"{start_label} - {end_label}"
    return start_label or end_label or "Dates not specified"


def _format_money(value: Any) -> str:
    amount = _number_or_none(value)
    if amount is None:
        return "Not specified"
    return f"${amount:,.2f}"


def _format_duration_minutes(value: Any) -> str:
    minutes = _number_or_none(value)
    if minutes is None:
        return ""
    return _format_minutes(int(round(minutes)))


def _format_duration_seconds(value: Any) -> str:
    seconds = _number_or_none(value)
    if seconds is None:
        return ""
    return _format_minutes(int(round(seconds / 60)))


def _format_minutes(minutes: int) -> str:
    if minutes <= 0:
        return ""
    hours, remainder = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hr")
    if remainder:
        parts.append(f"{remainder} min")
    return " ".join(parts) or "0 min"


def _format_distance_meters(value: Any) -> str:
    meters = _number_or_none(value)
    if meters is None:
        return ""
    miles = meters / 1609.344
    if miles < 0.15:
        return f"{meters * 3.28084:,.0f} ft"
    return f"{miles:.1f} mi"


def _humanize_key(key: str) -> str:
    if key in KEY_LABELS:
        return KEY_LABELS[key]
    text = re.sub(r"(?<!^)(?=[A-Z])", " ", key)
    text = text.replace("_", " ").replace("-", " ")
    return text.strip().title()


def _titleize(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return "Not specified"
    return text.replace("_", " ").replace("-", " ").title()


def _clean_day_title(title: str, day_number: int) -> str:
    cleaned = _clean_text(title)
    cleaned = re.sub(rf"^Day\s+{day_number}\s*[-:]\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned or f"Day {day_number}"


def _is_url(value: str) -> bool:
    return bool(value and re.match(r"^https?://", value, flags=re.IGNORECASE))


def _destination_names(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                value = parsed
            else:
                return [_clean_text(value)] if _clean_text(value) else []
        except Exception:
            return [_clean_text(value)] if _clean_text(value) else []
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        name = _location_name(item)
        if name:
            names.append(name)
    return names


def _location_name(value: Any) -> str:
    if isinstance(value, dict):
        return _first_text(value.get("city"), value.get("name"), value.get("formatted_address"), value.get("address"))
    return _clean_text(value)


def _route_label(origin: str, destinations: list[str]) -> str:
    if not destinations:
        return origin
    return f"{origin} / {' / '.join(destinations)}"


def _journey_label(origin: str, destinations: list[str]) -> str:
    if not destinations:
        return origin
    return " / ".join([origin, *destinations])


def _build_day_overviews(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    overviews: list[dict[str, Any]] = []
    for day in days:
        overview_events: list[dict[str, str]] = []
        for event in day.get("events", []):
            if event.get("event_type") == "COMMUTE":
                continue
            title = _first_text(event.get("title"), event.get("label"))
            if not title:
                continue
            overview_events.append(
                {
                    "time": _first_text(event.get("time_label"), "Flexible"),
                    "label": _first_text(event.get("label"), "Itinerary Item"),
                    "title": title,
                    "subtitle": _first_text(event.get("subtitle"), event.get("location")),
                    "cost": _first_text(event.get("cost"), ""),
                }
            )
        overviews.append(
            {
                "day_number": day.get("day_number"),
                "title": day.get("title"),
                "date_label": day.get("date_label"),
                "events": overview_events,
                "cost": day.get("cost"),
            }
        )
    return overviews


def _traveler_label(adults: int, children: int) -> str:
    parts = []
    if adults:
        parts.append(f"{adults} adult{'s' if adults != 1 else ''}")
    if children:
        parts.append(f"{children} child{'ren' if children != 1 else ''}")
    return ", ".join(parts) if parts else "Travelers not specified"


def _days_label(configured_days: Any, days: list[dict[str, Any]]) -> str:
    day_count = int(configured_days or len(days) or 0)
    if day_count <= 0:
        return "Not specified"
    return f"{day_count} day{'s' if day_count != 1 else ''}"


def _user_display_name(user: Any) -> str:
    if not user:
        return ""
    first = _attr(user, "first_name", "")
    last = _attr(user, "last_name", "")
    email = _attr(user, "email", "")
    return _first_text(f"{first or ''} {last or ''}", email)


def _airport_route(details: dict[str, Any]) -> str:
    departure = _first_text(details.get("departure_airport_code"), details.get("departure_airport_name"))
    arrival = _first_text(details.get("arrival_airport_code"), details.get("arrival_airport_name"))
    if departure and arrival:
        return f"{departure} to {arrival}"
    return departure or arrival


def _vehicle_name(value: Any) -> str:
    if isinstance(value, dict):
        return _first_text(value.get("vehicle_name"), value.get("group"))
    return _clean_text(value)


def _rating_label(details: dict[str, Any]) -> str:
    rating = _number_or_none(details.get("rating"))
    if rating is None:
        return ""
    return f"{rating:.1f} / 5"
