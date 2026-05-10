# backend/app/agent/api/v1/endpoints/solo_planner.py

"""
SSE endpoint for the solo planner.

Streams chunks from `generate_trip_itinerary` straight to the client with
zero backend buffering. Event chunks are persisted by a single background
DB-writer task so commits never stall the SSE stream. Finalization
(status updates + queue drain) runs under `asyncio.shield` so client
disconnects cannot leave the DB in a GENERATING state.
"""

import asyncio
import json
from typing import Any, Optional

import jwt

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agent.solo_planner import generate_trip_itinerary
from app.agent.helpers.itinerary_event_cost import sum_chargeable_cost_usd
from app.agent.langgraph_runtime.collaboration import (
    get_pending,
    submit_answer,
)
from app.agent.helpers.qa_persistence import load_collab_qa
from app.agent.langgraph_runtime.editing.snapshot_service import ensure_initial_snapshot
from app.core.config import settings
from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary, TripItineraryStatus
from app.database.models.tripMembersTable import TripInvitationStatus, TripMember
from app.database.models.tripsTable import PlanStatus, Trip
from app.logging import get_api_logger

logger = get_api_logger("solo_planner")

router = APIRouter()


# Strong references to detached finalize tasks so the event loop keeps
# them alive until they finish. asyncio.create_task only keeps weak refs
# internally; without this a task can be GC'd mid-execution when the
# response generator unwinds from a client disconnect.
_pending_finalize_tasks: set[asyncio.Task] = set()

# Render free instances typically run a single worker process, so an
# in-memory guard is enough to prevent two clients from generating the
# same trip at the same time.
_active_generations: set[str] = set()
_active_generations_lock = asyncio.Lock()


async def _claim_generation(trip_id: str) -> bool:
    async with _active_generations_lock:
        if trip_id in _active_generations:
            return False
        _active_generations.add(trip_id)
        return True


async def _release_generation(trip_id: str) -> None:
    async with _active_generations_lock:
        _active_generations.discard(trip_id)


async def _apply_lock_updates(trip_id: str, updates: list) -> None:
    """Patch is_locked on already-saved events without touching other fields."""
    if not updates:
        return
    async with Session() as db:
        itinerary = (
            await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip_id))
        ).scalar_one_or_none()
        if itinerary is None:
            return
        events = list(itinerary.events or [])
        index = {(e.get("day_number"), e.get("event_number")): i for i, e in enumerate(events)}
        changed = False
        for upd in updates:
            key = (upd.get("day_number"), upd.get("event_number"))
            idx = index.get(key)
            if idx is not None:
                events[idx] = {**events[idx], "is_locked": upd.get("is_locked")}
                changed = True
        if changed:
            itinerary.events = events
            await db.commit()


def _remove_events_from_list(events: list, day_number: int, from_event_number: int) -> list:
    """Drop regular events on one day from a retry point onward."""
    return [
        event
        for event in events
        if not (
            event.get("event_type") not in ("START", "END")
            and event.get("day_number") == day_number
            and isinstance(event.get("event_number"), int)
            and event["event_number"] >= from_event_number
        )
    ]


async def _apply_event_removal(
    trip_id: str,
    day_number: int,
    from_event_number: int,
) -> None:
    """Remove stale events that the validator stripped before a retry."""
    async with Session() as db:
        itinerary = (
            await db.execute(select(TripItinerary).where(TripItinerary.trip_id == trip_id))
        ).scalar_one_or_none()
        if itinerary is None:
            return
        events = list(itinerary.events or [])
        next_events = _remove_events_from_list(events, day_number, from_event_number)
        if len(next_events) == len(events):
            return
        itinerary.events = next_events
        await db.commit()


async def _apply_event_write(trip_id: str, event: dict) -> None:
    """Persist a single itinerary event chunk to the DB."""
    event_type = event.get("event_type")

    async with Session() as db:
        itinerary = (
            await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == trip_id)
            )
        ).scalar_one_or_none()
        if itinerary is None:
            return

        if event_type == "START":
            start_details = event.get("start_details") or {}
            itinerary.title = start_details.get("trip_title", itinerary.title)
            itinerary.destinations = start_details.get(
                "journey", itinerary.destinations
            )
            itinerary.days = start_details.get("number_of_days", itinerary.days)
            itinerary.cost = start_details.get(
                "trip_cost_estimate", itinerary.cost
            )
            # Persist to events so resume detection can find it.
            if not any(e.get("event_type") == "START" for e in (itinerary.events or [])):
                itinerary.events = list(itinerary.events or [])
                itinerary.events.append(event)
            else:
                existing_start_event_index = None
                for i, existing_event in enumerate(itinerary.events):
                    if existing_event.get("event_type") == "START":
                        existing_start_event_index = i
                        break
                if existing_start_event_index is not None:
                    itinerary.events[existing_start_event_index] = event
        elif event_type == "END":
            end_details = dict(event.get("end_details") or {})
            itinerary.title = end_details.get("trip_title", itinerary.title)
            itinerary.tips = end_details.get("trip_tips", itinerary.tips)
            # Persist to events so the full event record is available on load.
            if not any(e.get("event_type") == "END" for e in (itinerary.events or [])):
                itinerary.events = list(itinerary.events or [])
                itinerary.events.append(event)
            else:
                existing_end_event_index = None
                for i, existing_event in enumerate(itinerary.events):
                    if existing_event.get("event_type") == "END":
                        existing_end_event_index = i
                        break
                if existing_end_event_index is not None:
                    itinerary.events[existing_end_event_index] = event
            # Align column + END payload with summed event charges (frontend uses the same rollup).
            rolled_up = sum_chargeable_cost_usd(itinerary.events)
            itinerary.cost = rolled_up
            end_details["trip_cost"] = rolled_up
            event["end_details"] = end_details
        else:
            existing_event_index = None
            for i, existing_event in enumerate(itinerary.events):
                if existing_event.get("day_number") == event.get("day_number") and existing_event.get("event_number") == event.get("event_number"):
                    existing_event_index = i
                    break
            if existing_event_index is None:
                    itinerary.events.append(event)
            else:
                itinerary.events[existing_event_index] = event

        await db.commit()


@router.post("/generate/solo/{id}")
async def generate_solo_plan(request: Request, id: str):
    # 1. Validate token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header."
        )
    token = auth_header.split(" ")[1]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(
            status_code=401, detail="Invalid session. Please log in again."
        )

    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    if not await _claim_generation(id):
        raise HTTPException(
            status_code=409,
            detail="This trip is already generating. Wait for the current run to finish.",
        )

    # 2. Body
    try:
        body = await request.json()
        chat_input = body.get("chatInput", "")
        mode = body.get("mode", "autonomous")
        use_fast_model = bool(body.get("use_fast_model", False))
    except Exception:
        chat_input = ""
        mode = "autonomous"
        use_fast_model = False

    # 3. RBAC + flip statuses to GENERATING + assemble payload
    current_trip_itinerary: Optional[list] = None
    try:
        async with Session() as db:
            rbac = (
                await db.execute(
                    select(TripMember).where(
                        TripMember.trip_id == id,
                        TripMember.user_id == user_id,
                        TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                    )
                )
            ).scalar_one_or_none()
            if not rbac or rbac.role not in ["owner", "shared_editor"]:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to generate or edit this plan.",
                )

            plan = (
                await db.execute(select(Trip).where(Trip.id == id))
            ).scalar_one_or_none()
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found.")

            plan.status = PlanStatus.GENERATING

            itinerary_row = (
                await db.execute(
                    select(TripItinerary).where(TripItinerary.trip_id == id)
                )
            ).scalar_one_or_none()
            _smart_anchors: list = []
            if itinerary_row:
                current_trip_itinerary = itinerary_row.events
                itinerary_row.status = TripItineraryStatus.GENERATING
                _smart_anchors = itinerary_row.smart_anchors or []

            await db.commit()

            # Load full Q&A history for collaborative mode.
            # Seed answer → injected into state so checkpoint doesn't re-ask.
            # All pairs → injected as prior_qa_pairs so day planners don't
            # repeat questions and apply prior session preferences.
            _collab_seed_answer: Optional[str] = None
            _collab_qa_pairs: list = []
            if mode == "collaborative":
                _collab_qa_pairs = await load_collab_qa(str(id), str(user_id))
                for entry in _collab_qa_pairs:
                    if entry.get("context") == "seed":
                        _collab_seed_answer = (
                            "(no preference — surprise me)"
                            if entry.get("skipped")
                            else entry.get("answer") or None
                        )
                        break

            destinations_list = plan.destinations
            if isinstance(destinations_list, str):
                try:
                    destinations_list = json.loads(destinations_list)
                except Exception:
                    destinations_list = []

            start_date = (
                json.loads(plan.start_date)
                if isinstance(plan.start_date, str)
                else plan.start_date
            )
            end_date = (
                json.loads(plan.end_date)
                if isinstance(plan.end_date, str)
                else plan.end_date
            )

            # Derive the outer SSE timeout budget: 6 minutes per trip day with
            # a 2-minute floor and a 60-minute hard ceiling. This protects us
            # from a stuck run tying up a connection indefinitely while still
            # letting long multi-city trips finish.
            try:
                _s_ts = int(start_date.get("utcTimestamp", 0)) if isinstance(start_date, dict) else 0
                _e_ts = int(end_date.get("utcTimestamp", 0)) if isinstance(end_date, dict) else 0
                _trip_days = max(1, (_e_ts - _s_ts) // 86400)
            except Exception:
                _trip_days = 1
            sse_timeout_seconds = max(120, min(6 * 60 * _trip_days, 60 * 60))

            trip_payload = {
                "hasMultipleDestinations": len(destinations_list) > 1,
                "planning_type": plan.planning_type.value
                if hasattr(plan.planning_type, "value")
                else plan.planning_type,
                "routing_style": plan.routing_style.value
                if hasattr(plan.routing_style, "value")
                else plan.routing_style,
                "origin": json.loads(plan.origin)
                if isinstance(plan.origin, str)
                else plan.origin,
                "destinations": destinations_list,
                "start_date": start_date,
                "end_date": end_date,
                "pace": plan.pace,
                "budget": plan.budget,
                "adults": plan.adults,
                "children": plan.children,
                "preferences": rbac.trip_preferences or {},
                "textualContext": chat_input,
                "smart_anchors": _smart_anchors,
            }
    except HTTPException:
        await _release_generation(id)
        raise
    except Exception as e:
        logger.error("Failed to generate solo plan", trip_id=id, error=str(e))
        # Best-effort status revert if row exists.
        try:
            async with Session() as db:
                plan_row = (
                    await db.execute(select(Trip).where(Trip.id == id))
                ).scalar_one_or_none()
                if plan_row:
                    plan_row.status = PlanStatus.DRAFT
                    await db.flush()
                itinerary_row = (
                    await db.execute(select(TripItinerary).where(TripItinerary.trip_id == id))
                ).scalar_one_or_none()
                if itinerary_row:
                    itinerary_row.status = TripItineraryStatus.GENERATING
                    await db.flush()
                await db.commit()
        except Exception:
            pass
        await _release_generation(id)
        raise HTTPException(
            status_code=500, detail=f"Failed to assemble Trip data: {e}"
        )

    # 4. Streaming wrapper
    async def event_generator():
        write_queue: asyncio.Queue = asyncio.Queue()
        success = False

        async def db_writer():
            while True:
                item = await write_queue.get()
                try:
                    if item is None:
                        return
                    try:
                        # Lock-update marker — patch is_locked only.
                        if isinstance(item, dict) and item.get("__lock_update"):
                            await _apply_lock_updates(str(id), item.get("updates", []))
                        elif isinstance(item, dict) and item.get("__events_removed"):
                            await _apply_event_removal(
                                str(id),
                                int(item.get("day_number")),
                                int(item.get("from_event_number")),
                            )
                        else:
                            await _apply_event_write(str(id), item)
                    except Exception as e:
                        logger.exception("SSE DB write failed", error=str(e))
                finally:
                    write_queue.task_done()

        writer_task: asyncio.Task = asyncio.create_task(db_writer())

        async def finalize(success_flag: bool):
            # Drain the writer: push sentinel and wait for it to exit.
            try:
                await write_queue.put(None)
            except Exception:
                pass
            try:
                await writer_task
            except Exception as e:
                logger.warning("SSE writer task raised on drain", error=str(e))

            # Update terminal statuses and create initial snapshot on success.
            try:
                async with Session() as db:
                    plan_row = (
                        await db.execute(select(Trip).where(Trip.id == id))
                    ).scalar_one_or_none()
                    itin_row = (
                        await db.execute(
                            select(TripItinerary).where(TripItinerary.trip_id == id)
                        )
                    ).scalar_one_or_none()
                    if plan_row and itin_row:
                        if success_flag:
                            plan_row.status = PlanStatus.GENERATED
                            itin_row.status = TripItineraryStatus.GENERATED
                            await db.flush()
                            # Persist version_index=0 snapshot so the edit/revert
                            # flow always has the original generation to fall back to.
                            await ensure_initial_snapshot(
                                db,
                                trip_id=str(id),
                                itinerary=itin_row,
                                prepared_events=list(itin_row.events or []),
                            )
                        else:
                            plan_row.status = PlanStatus.DRAFT
                            itin_row.status = TripItineraryStatus.PENDING
                        await db.commit()
            except Exception as e:
                logger.exception("SSE failed to update final statuses", error=str(e))

        try:
            gen = generate_trip_itinerary(
                trip_payload,
                mode=mode,
                current_trip_itinerary=current_trip_itinerary,
                user_id=str(user_id),
                trip_id=str(id),
                cancellation_callback=request.is_disconnected,
                collab_seed_answer=_collab_seed_answer,
                collab_qa_pairs=_collab_qa_pairs,
                use_fast_model=use_fast_model,
            )

            # Outer timeout: each `anext()` bounded by `sse_timeout_seconds`.
            # Framing it as a per-iteration timeout is more useful than one
            # global deadline because it surfaces stuck turns quickly while
            # letting healthy runs proceed naturally for long trips.
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        gen.__anext__(), timeout=sse_timeout_seconds
                    )
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    logger.warning(
                        "SSE stream idle — aborting",
                        timeout_s=sse_timeout_seconds, trip_id=str(id),
                    )
                    success = False
                    try:
                        yield f"data: {json.dumps({'type': 'error', 'content': 'Generation timed out — please try again.'})}\n\n"
                    except Exception:
                        pass
                    try:
                        await gen.aclose()
                    except Exception:
                        pass
                    break

                chunk_type = chunk.get("type")

                # Queue DB work before forwarding. This does not wait for the
                # commit, but it does ensure a client disconnect after receiving
                # a chunk cannot skip the corresponding persistence action.
                if chunk_type == "event":
                    event_data = chunk.get("data") or {}
                    if event_data:
                        await write_queue.put(event_data)
                elif chunk_type == "lock_update":
                    updates = chunk.get("updates") or []
                    if updates:
                        await write_queue.put({"__lock_update": True, "updates": updates})
                elif chunk_type == "events_removed":
                    day_number = chunk.get("day_number")
                    from_event_number = chunk.get("from_event_number")
                    if isinstance(day_number, int) and isinstance(from_event_number, int):
                        await write_queue.put({
                            "__events_removed": True,
                            "day_number": day_number,
                            "from_event_number": from_event_number,
                        })

                if chunk_type == "summary":
                    # Any summary text means the agent reached END and is
                    # finalizing. Mark success; more summary chunks may follow.
                    success = True
                elif chunk_type == "error":
                    success = False

                yield f"data: {json.dumps(chunk)}\n\n"

                if chunk_type == "error":
                    break

        except asyncio.CancelledError:
            logger.info("SSE client disconnected — finalizing", trip_id=str(id))
            # Fall through to the shielded finalize in the finally block.
            raise
        except Exception as e:
            logger.exception("SSE unexpected error while streaming", trip_id=str(id), error=str(e))
            success = False
            try:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            except Exception:
                pass
        finally:
            # Schedule finalize as a detached task tracked at module level
            # so the event loop keeps a strong reference to it. This is
            # critical for the client-disconnect path: the response task
            # is being cancelled here, and any `await` on the finalize
            # task from a cancelled parent would propagate cancellation
            # into it (even through asyncio.shield, once the parent is
            # already in cancelled state). By detaching it and not
            # awaiting on the cancel path, we let it run to completion
            # on the event loop and write the final statuses.
            finalize_task = asyncio.create_task(finalize(success))
            _pending_finalize_tasks.add(finalize_task)
            finalize_task.add_done_callback(_pending_finalize_tasks.discard)

            # Best-effort: on the non-cancelled path, wait for finalize
            # so the response doesn't close before the DB is updated.
            # On the cancelled path, the await will raise and we swallow
            # it — the task itself keeps running in the background.
            try:
                await asyncio.shield(finalize_task)
            except BaseException as e:
                if not isinstance(e, asyncio.CancelledError):
                    logger.warning(
                        "SSE finalize raised (will still complete in background)",
                        trip_id=str(id), error=str(e),
                    )
                # Do NOT re-raise here; the outer except already handled
                # the original exception. The finally's job is just to
                # guarantee finalize was scheduled.
            finally:
                await _release_generation(str(id))

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/generate/solo/{id}/respond")
async def respond_to_question(request: Request, id: str):
    """
    Deliver a user's answer to the currently-pending collaborative question
    for *id*. The matching chat-loop coroutine in the SSE stream awakens
    and continues. The SSE stream itself stays open and is the only path
    further chunks flow on.

    Status codes:
      200 — answer accepted
      400 — malformed body or sanitization rejected the answer
      401 — unauthenticated
      403 — caller is not owner/shared_editor of the trip
      404 — no pending question for this trip
      409 — call_id mismatch (stale tab) or the question was already answered
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header."
        )
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(
            status_code=401, detail="Invalid session. Please log in again."
        )
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    call_id = body.get("call_id")
    answer = body.get("answer")
    skipped = bool(body.get("skipped", False))
    if not isinstance(call_id, str) or not call_id:
        raise HTTPException(status_code=400, detail="`call_id` is required.")

    # RBAC check.
    async with Session() as db:
        rbac = (
            await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == id,
                    TripMember.user_id == user_id,
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )
        ).scalar_one_or_none()
        if not rbac or rbac.role not in ["owner", "shared_editor"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to answer questions for this plan.",
            )

    # Quick existence check before submitting (gives a precise 404 vs the
    # generic 'stale_question' that submit_answer returns for any mismatch).
    if get_pending(str(id)) is None:
        raise HTTPException(status_code=404, detail="No pending question for this trip.")

    status, detail = submit_answer(str(id), call_id, answer, skipped)
    if status == "ok":
        return {"ok": True}
    if status == "not_found":
        raise HTTPException(status_code=404, detail=detail or "not_found")
    if status == "stale":
        raise HTTPException(status_code=409, detail=detail or "stale_question")
    if status == "invalid":
        raise HTTPException(status_code=400, detail=detail or "invalid_answer")
    # Defensive default — shouldn't be reachable.
    raise HTTPException(status_code=500, detail="Unknown submit_answer status.")
