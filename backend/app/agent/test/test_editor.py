"""
Interactive and smoke-test harness for itinerary chat/editing.

Run from backend/:
    python -m app.agent.test.test_editor --random
    python -m app.agent.test.test_editor --trip-id <uuid>
    python -m app.agent.test.test_editor --smoke --max-cases 6
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.agent.core.runtime import agent_runtime_context
from app.agent.editor_planner import run_editor_chat
from app.agent.langgraph_runtime.editing.event_utils import (
    canonicalize_events,
    ensure_event_identities,
    event_name,
    events_hash,
    is_locked,
    regular_events,
)
from app.agent.langgraph_runtime.editing.snapshot_service import (
    EditConflictError,
    list_snapshots,
    revert_to_snapshot,
)
from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary, TripItineraryStatus
from app.database.models.tripMembersTable import TripInvitationStatus, TripMember, TripRole
from app.database.models.tripsTable import PlanStatus, Trip


def _role_value(role: Any) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _status_value(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _format_chunk(chunk: Dict[str, Any]) -> str:
    ctype = chunk.get("type", "unknown")
    if ctype in {"thinking", "summary", "error"}:
        content = (chunk.get("content") or "").strip()
        return f"[{ctype}] {content}" if content else f"[{ctype}]"
    if ctype == "tool_call":
        return f"[tool_call] {chunk.get('tool_name')} {chunk.get('args') or {}}"
    if ctype == "tool_response":
        return f"[tool_response] {chunk.get('tool_name')} {chunk.get('response') or {}}"
    if ctype == "intent":
        return f"[intent] {chunk.get('value')}"
    if ctype == "structural_change":
        return f"[structural_change] {chunk.get('reason') or ''}".rstrip()
    if ctype == "edit_status":
        return f"[edit_status] {chunk.get('status')} trip={chunk.get('trip_status')}"
    if ctype == "edit_clarification":
        return f"[edit_clarification] {chunk.get('question')}"
    if ctype == "edit_rejected":
        suffix = " conflict=true" if chunk.get("conflict") else ""
        reason = chunk.get("reason") or ""
        errors = chunk.get("validation_errors") or []
        if errors:
            reason += " | " + " ; ".join(str(e) for e in errors[:3])
        return f"[edit_rejected{suffix}] {reason}"
    if ctype == "itinerary_replace":
        return (
            f"[itinerary_replace] events={len(chunk.get('events') or [])} "
            f"cursor={chunk.get('snapshot_cursor')} hash={str(chunk.get('events_hash') or '')[:10]}"
        )
    if ctype == "edit_commit":
        return (
            f"[edit_commit] cursor={chunk.get('snapshot_cursor')} "
            f"hash={str(chunk.get('events_hash') or '')[:10]} {chunk.get('summary') or ''}"
        ).strip()
    if ctype == "edit_end":
        return f"[edit_end] {chunk.get('status')}"
    if ctype == "conversation_end":
        return "[conversation_end]"
    if ctype == "heartbeat":
        return "[heartbeat]"
    return json.dumps(chunk, default=str)


async def _choose_trip_context(explicit_trip_id: Optional[str] = None) -> Optional[dict]:
    async with Session() as db:
        if explicit_trip_id:
            trip = (await db.execute(select(Trip).where(Trip.id == explicit_trip_id))).scalar_one_or_none()
            if not trip:
                return None
            return await _context_for_trip(db, trip)

        trips = (
            await db.execute(
                select(Trip)
                .where(Trip.status == PlanStatus.GENERATED)
                .order_by(Trip.updated_at.desc())
            )
        ).scalars().all()
        trips = list(trips)
        random.shuffle(trips)
        for trip in trips:
            context = await _context_for_trip(db, trip)
            if context:
                return context
    return None


async def _context_for_trip(db, trip: Trip) -> Optional[dict]:
    itinerary = (
        await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip.id))
    ).scalar_one_or_none()
    if itinerary is None or _status_value(itinerary.status) != TripItineraryStatus.GENERATED.value:
        return None
    if not itinerary.events:
        return None
    member = (
        await db.execute(
            select(TripMember)
            .where(
                TripMember.trip_id == trip.id,
                TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
            )
            .order_by(TripMember.created_at.asc())
        )
    ).scalars().first()
    if member and _role_value(member.role) not in {TripRole.OWNER.value, TripRole.SHARED_EDITOR.value}:
        return None
    return {
        "trip_id": str(trip.id),
        "user_id": str(member.user_id if member and member.user_id else trip.owner_id),
        "events_count": len(itinerary.events or []),
    }


async def _load_cached_context(trip_id: str, user_id: str) -> Optional[dict]:
    async with Session() as db:
        itinerary = (
            await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip_id))
        ).scalar_one_or_none()
        trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
        member = (
            await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == trip_id,
                    TripMember.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    if itinerary is None or trip is None:
        return None

    destinations = trip.destinations
    if isinstance(destinations, str):
        try:
            destinations = json.loads(destinations)
        except Exception:
            destinations = []

    prepared_events, _ = ensure_event_identities(itinerary.events or [])
    prepared_events = canonicalize_events(prepared_events, include_display_numbers=True)
    trip_input = {
        "hasMultipleDestinations": len(destinations) > 1,
        "planning_type": trip.planning_type.value if hasattr(trip.planning_type, "value") else trip.planning_type,
        "routing_style": trip.routing_style.value if hasattr(trip.routing_style, "value") else trip.routing_style,
        "origin": trip.origin,
        "destinations": destinations,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "pace": trip.pace,
        "budget": trip.budget,
        "adults": trip.adults,
        "children": trip.children,
        "preferences": (member.trip_preferences or {}) if member else {},
        "textualContext": "",
        "smart_anchors": itinerary.smart_anchors or [],
    }
    return {
        "events": prepared_events,
        "trip_input": trip_input,
        "research_facts": {},
        "snapshot_cursor": int(itinerary.snapshot_cursor or 0),
        "events_hash": events_hash(prepared_events),
        "trip_status": _status_value(trip.status),
        "itinerary_status": _status_value(itinerary.status),
        "cost": itinerary.cost,
        "title": itinerary.title,
    }


async def _verify_db_state(
    *,
    trip_id: str,
    expected_hash: Optional[str] = None,
) -> None:
    async with Session() as db:
        trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
        itinerary = (
            await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip_id))
        ).scalar_one_or_none()
    if trip is None or itinerary is None:
        print("[verify] trip/itinerary missing")
        return
    trip_status = _status_value(trip.status)
    itin_status = _status_value(itinerary.status)
    prepared, _ = ensure_event_identities(itinerary.events or [])
    current_hash = events_hash(prepared)
    status_ok = trip_status == PlanStatus.GENERATED.value and itin_status == TripItineraryStatus.GENERATED.value
    hash_ok = expected_hash is None or expected_hash == current_hash
    print(
        f"[verify] trip_status={trip_status} itinerary_status={itin_status} "
        f"cursor={itinerary.snapshot_cursor} hash={current_hash[:10]} "
        f"status_ok={status_ok} hash_ok={hash_ok}"
    )


def _print_events(events: list[dict[str, Any]], day_filter: Optional[int] = None) -> None:
    rows = regular_events(events, day_filter)
    if not rows:
        print("No regular events found.")
        return
    for event in rows:
        lock = " locked" if is_locked(event) else ""
        display = event.get("display_event_number", event.get("event_number"))
        print(
            f"Day {event.get('day_number')} display {display} legacy {event.get('event_number')} "
            f"{event.get('event_type')}{lock} id={event.get('event_id')} :: {event_name(event)}"
        )


async def _print_snapshots(trip_id: str) -> None:
    async with Session() as db:
        snapshots = await list_snapshots(db, trip_id=trip_id)
        itinerary = (
            await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip_id))
        ).scalar_one_or_none()
    print(f"snapshot_cursor={getattr(itinerary, 'snapshot_cursor', None)} snapshots={len(snapshots)}")
    for snapshot in snapshots:
        print(
            f"  v{snapshot['version_index']} events={snapshot['events_count']} "
            f"cost={snapshot['cost']} created={snapshot['created_at']} :: {snapshot.get('description') or ''}"
        )


async def _revert(trip_id: str, version_index: int) -> bool:
    async with Session() as db:
        try:
            result = await revert_to_snapshot(db, trip_id=trip_id, version_index=version_index)
            print(f"[revert] restored cursor={result.snapshot_cursor} hash={result.events_hash[:10]} events={len(result.events)}")
            return True
        except EditConflictError as exc:
            await db.rollback()
            print(f"[revert] {exc}")
            return False
        except Exception as exc:
            await db.rollback()
            print(f"[revert:error] {exc}")
            return False


async def _run_one_message(
    *,
    trip_id: str,
    user_id: str,
    user_message: str,
    cached_context: dict,
    chat_history: list[dict[str, str]],
    attached_events: list[dict[str, Any]],
    force_reload: bool = True,
) -> list[dict[str, Any]]:
    print(f"\nyou> {user_message}")
    print("assistant>")
    chunks: list[dict[str, Any]] = []
    expected_hash: Optional[str] = None
    async for chunk in run_editor_chat(
        trip_id=trip_id,
        user_message=user_message,
        user_id=user_id,
        chat_history=chat_history,
        attached_events=attached_events,
        cached_itinerary_events=cached_context.get("events") or [],
        cached_trip_input=cached_context.get("trip_input") or {},
        cached_research_facts=cached_context.get("research_facts") or {},
        base_snapshot_cursor=cached_context.get("snapshot_cursor"),
        base_events_hash=cached_context.get("events_hash"),
        force_reload_itinerary=force_reload,
    ):
        chunks.append(chunk)
        if chunk.get("type") in {"itinerary_replace", "edit_commit"} and chunk.get("events_hash"):
            expected_hash = chunk.get("events_hash")
        print(_format_chunk(chunk))

    assistant_text = " ".join(
        (chunk.get("content") or chunk.get("summary") or chunk.get("reason") or chunk.get("question") or "").strip()
        for chunk in chunks
        if chunk.get("type") in {"summary", "edit_commit", "edit_rejected", "edit_clarification"}
    ).strip()
    chat_history.extend([
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_text},
    ])
    await _verify_db_state(trip_id=trip_id, expected_hash=expected_hash)
    return chunks


async def _run_interactive(trip_id: str, user_id: str, cached_context: dict) -> None:
    print(
        "\nCommands: /events [day], /attach <day> <event>, /attach-id <event_id>, "
        "/clear-attachments, /snapshots, /revert <version>, /reload, /status, /smoke, /exit\n"
    )
    chat_history: List[Dict[str, str]] = []
    attached_events: List[Dict[str, Any]] = []

    while True:
        try:
            raw = input("you> ").strip()
        except EOFError:
            break
        if not raw:
            continue
        lower = raw.lower()
        if lower in {"/exit", "exit", "quit"}:
            break
        if lower == "/clear":
            os.system("clear")
            continue
        if lower.startswith("/events"):
            parts = raw.split()
            day = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            _print_events(cached_context.get("events") or [], day)
            continue
        if lower.startswith("/attach-id"):
            parts = raw.split(maxsplit=1)
            if len(parts) != 2:
                print("Usage: /attach-id <event_id>")
                continue
            attached_events = [{"event_id": parts[1].strip()}]
            print(f"attached event_id={parts[1].strip()}")
            continue
        if lower.startswith("/attach"):
            parts = raw.split()
            if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
                print("Usage: /attach <day> <event>")
                continue
            attached_events = [{"day_number": int(parts[1]), "event_number": int(parts[2])}]
            print(f"attached day={parts[1]} event={parts[2]}")
            continue
        if lower == "/clear-attachments":
            attached_events = []
            print("attachments cleared")
            continue
        if lower == "/snapshots":
            await _print_snapshots(trip_id)
            continue
        if lower.startswith("/revert"):
            parts = raw.split()
            if len(parts) != 2 or not parts[1].isdigit():
                print("Usage: /revert <version_index>")
                continue
            await _revert(trip_id, int(parts[1]))
            cached_context = await _load_cached_context(trip_id, user_id) or cached_context
            continue
        if lower == "/reload":
            cached_context = await _load_cached_context(trip_id, user_id) or cached_context
            print(
                f"reloaded events={len(cached_context.get('events') or [])} "
                f"cursor={cached_context.get('snapshot_cursor')} hash={str(cached_context.get('events_hash'))[:10]}"
            )
            continue
        if lower == "/status":
            print(
                f"trip={cached_context.get('trip_status')} itinerary={cached_context.get('itinerary_status')} "
                f"cursor={cached_context.get('snapshot_cursor')} hash={str(cached_context.get('events_hash'))[:10]}"
            )
            continue
        if lower == "/smoke":
            await _run_smoke_cases(trip_id, user_id, max_cases=8)
            cached_context = await _load_cached_context(trip_id, user_id) or cached_context
            continue

        await _run_one_message(
            trip_id=trip_id,
            user_id=user_id,
            user_message=raw,
            cached_context=cached_context,
            chat_history=chat_history,
            attached_events=attached_events,
        )
        cached_context = await _load_cached_context(trip_id, user_id) or cached_context


def _first_locked(events: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return next((event for event in regular_events(events) if is_locked(event)), None)


def _first_unlocked_flexible(events: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return next(
        (
            event for event in regular_events(events)
            if not is_locked(event) and event.get("event_type") in {"ACTIVITY", "DINING", "OTHER"}
        ),
        None,
    )


async def _run_smoke_cases(trip_id: str, user_id: str, max_cases: int) -> None:
    baseline = await _load_cached_context(trip_id, user_id)
    if not baseline:
        print("Could not load baseline.")
        return
    baseline_cursor = int(baseline.get("snapshot_cursor") or 0)
    print(
        f"[smoke] baseline cursor={baseline_cursor} hash={str(baseline.get('events_hash'))[:10]} "
        f"events={len(baseline.get('events') or [])}"
    )

    chat_history: list[dict[str, str]] = []
    cases: list[tuple[str, list[dict[str, Any]]]] = [
        ("What is the first event on this itinerary?", []),
        ("Change the destination to Tokyo.", []),
        ("Change the restaurant.", []),
    ]

    locked = _first_locked(baseline.get("events") or [])
    if locked:
        cases.append(("Remove this locked event.", [{"event_id": locked.get("event_id")}]))

    first_day = next((event.get("day_number") for event in regular_events(baseline.get("events") or []) if event.get("day_number")), 1)
    cases.append((f"Add a 30 minute coffee break at the end of day {first_day}.", []))

    flexible = _first_unlocked_flexible(baseline.get("events") or [])
    if flexible:
        cases.append(("Shorten this event to 30 minutes.", [{"event_id": flexible.get("event_id")}]))
        cases.append(("Move this event to the end of its day.", [{"event_id": flexible.get("event_id")}]))

    committed = False
    try:
        for idx, (message, attachments) in enumerate(cases[:max_cases], start=1):
            context = await _load_cached_context(trip_id, user_id) or baseline
            print(f"\n[smoke:{idx}/{min(len(cases), max_cases)}]")
            chunks = await _run_one_message(
                trip_id=trip_id,
                user_id=user_id,
                user_message=message,
                cached_context=context,
                chat_history=chat_history,
                attached_events=attachments,
            )
            if any(chunk.get("type") == "edit_commit" for chunk in chunks):
                committed = True
    finally:
        latest = await _load_cached_context(trip_id, user_id)
        if committed and latest and int(latest.get("snapshot_cursor") or 0) != baseline_cursor:
            print(f"\n[smoke] reverting to baseline cursor {baseline_cursor}")
            await _revert(trip_id, baseline_cursor)
            await _verify_db_state(trip_id=trip_id)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive itinerary editor smoke test")
    parser.add_argument("--trip-id", dest="trip_id", default=None, help="Use a specific trip id")
    parser.add_argument("--random", action="store_true", help="Pick a random generated trip")
    parser.add_argument("--message", default=None, help="Run one message and exit")
    parser.add_argument("--smoke", action="store_true", help="Run automated smoke cases and exit")
    parser.add_argument("--max-cases", type=int, default=8, help="Max automated smoke cases")
    args = parser.parse_args()

    context = await _choose_trip_context(args.trip_id)
    if not context:
        print("No generated trip with an itinerary and editable member was found.")
        return

    cached_context = await _load_cached_context(context["trip_id"], context["user_id"])
    if not cached_context:
        print("Could not load itinerary context for the selected trip.")
        return

    print(
        f"Using trip_id={context['trip_id']} user_id={context['user_id']} "
        f"events={context['events_count']} cursor={cached_context.get('snapshot_cursor')} "
        f"hash={str(cached_context.get('events_hash'))[:10]}"
    )

    async with agent_runtime_context():
        if args.smoke:
            await _run_smoke_cases(context["trip_id"], context["user_id"], args.max_cases)
            return
        if args.message:
            await _run_one_message(
                trip_id=context["trip_id"],
                user_id=context["user_id"],
                user_message=args.message,
                cached_context=cached_context,
                chat_history=[],
                attached_events=[],
            )
            return
        await _run_interactive(context["trip_id"], context["user_id"], cached_context)


if __name__ == "__main__":
    asyncio.run(main())
