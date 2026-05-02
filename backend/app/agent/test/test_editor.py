"""
Interactive itinerary chat smoke test.

This is a live terminal harness for the simplified editor graph:
intent_classifier -> editor_bootstrap -> structural_classifier -> conversational

It lets you pick a trip and talk to the graph in real time, which is the
style you asked for.
"""

import argparse
import asyncio
import json
import os
import random
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.agent.core.runtime import agent_runtime_context
from app.agent.editor_planner import run_editor_chat
from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary
from app.database.models.tripMembersTable import TripMember
from app.database.models.tripsTable import Trip


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
            itinerary = (
                await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip.id))
            ).scalar_one_or_none()
            member = (
                await db.execute(select(TripMember).where(TripMember.trip_id == trip.id))
            ).scalars().first()
            if itinerary is None:
                return None
            return {
                "trip_id": str(trip.id),
                "user_id": str(member.user_id if member else trip.owner_id),
                "events_count": len(itinerary.events or []),
            }

        trips = (await db.execute(select(Trip))).scalars().all()
        random.shuffle(trips)
        for trip in trips:
            itinerary = (
                await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip.id))
            ).scalars().first()
            if itinerary is None:
                continue
            member = (
                await db.execute(select(TripMember).where(TripMember.trip_id == trip.id))
            ).scalars().first()
            return {
                "trip_id": str(trip.id),
                "user_id": str(member.user_id if member else trip.owner_id),
                "events_count": len(itinerary.events or []),
            }

    return None


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

    return {
        "events": list(itinerary.events or []),
        "trip_input": {
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
        },
        "research_facts": {},
    }


async def _run_chat_loop(trip_id: str, user_id: str, cached_context: dict) -> None:
    print("\nType messages and press Enter. Use /exit to quit, /clear to clear screen.\n")
    chat_history: List[Dict[str, str]] = []
    attached_events: List[Dict[str, Any]] = []

    while True:
        try:
            user_message = input("you> ").strip()
        except EOFError:
            break

        if not user_message:
            continue
        if user_message.lower() in {"/exit", "exit", "quit"}:
            break
        if user_message.lower() == "/clear":
            os.system("clear")
            continue

        print("assistant>")
        chunks: List[Dict[str, Any]] = []
        async for chunk in run_editor_chat(
            trip_id=trip_id,
            user_message=user_message,
            user_id=user_id,
            chat_history=chat_history,
            attached_events=attached_events,
            cached_itinerary_events=cached_context.get("events") or [],
            cached_trip_input=cached_context.get("trip_input") or {},
            cached_research_facts=cached_context.get("research_facts") or {},
            force_reload_itinerary=False,
        ):
            chunks.append(chunk)
            print(_format_chunk(chunk))

        chat_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": " ".join(
                    (chunk.get("content") or "").strip()
                    for chunk in chunks
                    if chunk.get("type") == "summary" and (chunk.get("content") or "").strip()
                )},
            ]
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive itinerary chat smoke test")
    parser.add_argument("--trip-id", dest="trip_id", default=None, help="Use a specific trip id")
    args = parser.parse_args()

    context = await _choose_trip_context(args.trip_id)
    if not context:
        print("No trip with an itinerary was found.")
        return

    cached_context = await _load_cached_context(context["trip_id"], context["user_id"])
    if not cached_context:
        print("Could not load itinerary context for the selected trip.")
        return

    print(f"Using trip_id={context['trip_id']} user_id={context['user_id']} events={context['events_count']}")

    async with agent_runtime_context():
        await _run_chat_loop(context["trip_id"], context["user_id"], cached_context)


if __name__ == "__main__":
    asyncio.run(main())
