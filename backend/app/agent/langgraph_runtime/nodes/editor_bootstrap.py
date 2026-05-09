"""Editor bootstrap node."""

import json
import uuid
from typing import Any, Dict, List

from sqlalchemy import select

from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.editing.event_utils import (
    ensure_event_identities,
    event_by_id,
    event_by_legacy_ref,
    events_hash,
)
from app.agent.langgraph_runtime.streaming import emit
from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary
from app.database.models.tripMembersTable import TripInvitationStatus, TripMember
from app.database.models.tripsTable import Trip
from app.logging import get_agent_logger, set_agent_log_context

log = get_agent_logger("editor_bootstrap")


def _resolve_attached_events(
    attached_events: List[Dict[str, Any]],
    current_events: List[Dict[str, Any]],
) -> list[dict]:
    resolved: list[dict] = []
    for item in attached_events:
        event_id = item.get("event_id") if isinstance(item, dict) else None
        day_number = item.get("day_number") if isinstance(item, dict) else None
        event_number = item.get("event_number") if isinstance(item, dict) else None
        event_data = None
        if isinstance(event_id, str) and event_id:
            event_data = event_by_id(current_events, event_id)
        if event_data is None and isinstance(day_number, int) and isinstance(event_number, int):
            event_data = event_by_legacy_ref(current_events, day_number, event_number)
        if event_data is None:
            continue
        day_number = event_data.get("day_number")
        event_number = event_data.get("event_number")
        resolved.append(
            {
                "event_id": event_data.get("event_id"),
                "day_number": day_number,
                "event_number": event_number,
                "event_data": event_data,
            }
        )
    return resolved


async def editor_bootstrap_node(state: EditorState) -> Dict[str, Any]:
    run_id = (
        (state.get("trip_id") + "-" + state.get("user_id"))
        if state.get("trip_id") and state.get("user_id")
        else str(uuid.uuid4())
    )
    set_agent_log_context(run_id=run_id, node="editor_bootstrap")

    trip_id = state.get("trip_id")

    if not trip_id:
        emit({"type": "error", "content": "Missing trip_id."})
        return {"cancelled": True}

    cached_events = state.get("cached_itinerary_events")
    cached_trip_input = state.get("cached_trip_input")
    force_reload = bool(state.get("force_reload_itinerary", False))

    if (
        not force_reload
        and state.get("intent") != "edit"
        and isinstance(cached_events, list)
        and isinstance(cached_trip_input, dict)
        and cached_trip_input
    ):
        prepared_events, _ = ensure_event_identities(cached_events)
        resolved_attached = _resolve_attached_events(
            list(state.get("attached_events") or []),
            prepared_events,
        )
        log.info(
            "Editor bootstrap using cached itinerary context",
            trip_id=str(trip_id),
            events=len(cached_events),
            attached_resolved=len(resolved_attached),
        )
        return {
            "current_itinerary_events": list(prepared_events),
            "trip_input": dict(cached_trip_input),
            "research_facts": dict(state.get("cached_research_facts") or {}),
            "smart_anchors": list(cached_trip_input.get("smart_anchors") or []),
            "snapshot_cursor": state.get("client_base_snapshot_cursor") or 0,
            "base_events_hash": state.get("client_base_events_hash") or events_hash(prepared_events),
            "attached_events": resolved_attached,
            "itinerary_context_loaded_from_cache": True,
        }

    call_id = str(uuid.uuid4())
    emit(
        {
            "type": "tool_call",
            "tool_name": "load_itinerary",
            "args": {"trip_id": str(trip_id)},
            "call_id": call_id,
            "content": "Loading itinerary...",
        }
    )

    async with Session() as db:
        itinerary = (
            await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip_id))
        ).scalar_one_or_none()
        trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
        member = (
            await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == trip_id,
                    TripMember.user_id == state.get("user_id"),
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )
        ).scalar_one_or_none()

    if itinerary is None or trip is None:
        emit({"type": "error", "content": "Trip or itinerary not found."})
        return {"cancelled": True}

    current_events, _identity_changed = ensure_event_identities(itinerary.events or [])
    current_hash = events_hash(current_events)

    client_cursor = state.get("client_base_snapshot_cursor")
    if state.get("intent") == "edit" and isinstance(client_cursor, int):
        db_cursor = int(itinerary.snapshot_cursor or 0)
        if client_cursor != db_cursor:
            msg = (
                "This itinerary changed since your view loaded. "
                "Reload the itinerary and try the edit again."
            )
            emit({"type": "edit_rejected", "reason": msg, "conflict": True})
            emit({"type": "summary", "content": msg})
            emit({"type": "edit_end", "status": "conflict"})
            return {"cancelled": True}

    destinations_list = trip.destinations
    if isinstance(destinations_list, str):
        try:
            destinations_list = json.loads(destinations_list)
        except Exception:
            destinations_list = []

    start_date = json.loads(trip.start_date) if isinstance(trip.start_date, str) else trip.start_date
    end_date = json.loads(trip.end_date) if isinstance(trip.end_date, str) else trip.end_date

    trip_payload = {
        "hasMultipleDestinations": len(destinations_list) > 1,
        "planning_type": trip.planning_type.value if hasattr(trip.planning_type, "value") else trip.planning_type,
        "routing_style": trip.routing_style.value if hasattr(trip.routing_style, "value") else trip.routing_style,
        "origin": json.loads(trip.origin) if isinstance(trip.origin, str) else trip.origin,
        "destinations": destinations_list,
        "start_date": start_date,
        "end_date": end_date,
        "pace": trip.pace,
        "budget": trip.budget,
        "adults": trip.adults,
        "children": trip.children,
        "preferences": (member.trip_preferences or {}) if member else {},
        "textualContext": state.get("user_message", ""),
        "smart_anchors": itinerary.smart_anchors or [],
    }

    resolved_attached = _resolve_attached_events(
        list(state.get("attached_events") or []),
        current_events,
    )

    log.info(
        "Editor bootstrap complete",
        trip_id=str(trip_id),
        events=len(current_events),
        attached_resolved=len(resolved_attached),
    )

    return {
        "current_itinerary_events": current_events,
        "trip_input": trip_payload,
        "research_facts": {},
        "smart_anchors": list(itinerary.smart_anchors or []),
        "snapshot_cursor": int(itinerary.snapshot_cursor or 0),
        "base_events_hash": current_hash,
        "attached_events": resolved_attached,
        "itinerary_context_loaded_from_cache": False,
    }
