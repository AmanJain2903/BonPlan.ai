"""Itinerary chat SSE endpoints."""

import asyncio
import json
from typing import Any

import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agent.editor_planner import run_editor_chat
from app.core.config import settings
from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary
from app.database.models.tripMembersTable import TripInvitationStatus, TripMember
from app.logging import get_api_logger

logger = get_api_logger("chat")
router = APIRouter()


def _extract_user_id(request: Request) -> str:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")
    return str(user_id)


async def _assert_trip_access(trip_id: str, user_id: str) -> None:
    async with Session() as db:
        rbac = (
            await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == trip_id,
                    TripMember.user_id == user_id,
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )
        ).scalar_one_or_none()
        if not rbac or rbac.role not in ["owner", "shared_editor"]:
            raise HTTPException(status_code=403, detail="Not authorized for this plan.")


@router.post("/{trip_id}")
async def chat_with_itinerary(request: Request, trip_id: str):
    user_id = _extract_user_id(request)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    message = body.get("message")
    attached_events = body.get("attached_events") or []
    chat_history = body.get("chat_history") or []
    cached_itinerary_events = body.get("cached_itinerary_events") or []
    cached_trip_input = body.get("cached_trip_input") or {}
    cached_research_facts = body.get("cached_research_facts") or {}
    force_reload_itinerary = bool(body.get("force_reload_itinerary", False))

    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="`message` is required.")
    if not isinstance(attached_events, list):
        raise HTTPException(status_code=400, detail="`attached_events` must be a list.")
    if not isinstance(chat_history, list):
        raise HTTPException(status_code=400, detail="`chat_history` must be a list.")
    if cached_itinerary_events and not isinstance(cached_itinerary_events, list):
        raise HTTPException(status_code=400, detail="`cached_itinerary_events` must be a list.")
    if cached_trip_input and not isinstance(cached_trip_input, dict):
        raise HTTPException(status_code=400, detail="`cached_trip_input` must be an object.")
    if cached_research_facts and not isinstance(cached_research_facts, dict):
        raise HTTPException(status_code=400, detail="`cached_research_facts` must be an object.")

    await _assert_trip_access(str(trip_id), str(user_id))

    async with Session() as db:
        itinerary = (
            await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == trip_id)
            )
        ).scalar_one_or_none()
        if itinerary is None:
            raise HTTPException(status_code=404, detail="Itinerary not found for this trip.")

    async def event_generator():
        try:
            gen = run_editor_chat(
                trip_id=str(trip_id),
                user_message=message,
                user_id=str(user_id),
                chat_history=chat_history,
                attached_events=attached_events,
                cached_itinerary_events=cached_itinerary_events,
                cached_trip_input=cached_trip_input,
                cached_research_facts=cached_research_facts,
                force_reload_itinerary=force_reload_itinerary,
                cancellation_callback=request.is_disconnected,
            )
            while True:
                chunk = await asyncio.wait_for(gen.__anext__(), timeout=120)
                yield f"data: {json.dumps(chunk)}\n\n"
        except StopAsyncIteration:
            pass
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Request timed out.'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
