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
from app.core.config import settings
from app.database.database import Session
from app.database.models.tripItinerariesTable import TripItinerary, TripItineraryStatus
from app.database.models.tripMembersTable import TripMember
from app.database.models.tripsTable import PlanStatus, Trip

router = APIRouter()


# Strong references to detached finalize tasks so the event loop keeps
# them alive until they finish. asyncio.create_task only keeps weak refs
# internally; without this a task can be GC'd mid-execution when the
# response generator unwinds from a client disconnect.
_pending_finalize_tasks: set[asyncio.Task] = set()


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
        elif event_type == "END":
            end_details = event.get("end_details") or {}
            itinerary.title = end_details.get("trip_title", itinerary.title)
            itinerary.cost = end_details.get("trip_cost", itinerary.cost)
            itinerary.tips = end_details.get("trip_tips", itinerary.tips)
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

    # 2. Body
    try:
        body = await request.json()
        chat_input = body.get("chatInput", "")
        mode = body.get("mode", "autonomous")
    except Exception:
        chat_input = ""
        mode = "autonomous"

    # 3. RBAC + flip statuses to GENERATING + assemble payload
    current_trip_itinerary: Optional[list] = None
    try:
        async with Session() as db:
            rbac = (
                await db.execute(
                    select(TripMember).where(
                        TripMember.trip_id == id, TripMember.user_id == user_id
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
            if itinerary_row:
                current_trip_itinerary = itinerary_row.events
                itinerary_row.status = TripItineraryStatus.GENERATING

            await db.commit()

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
            }
    except HTTPException:
        raise
    except Exception as e:
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
                        await _apply_event_write(str(id), item)
                    except Exception as e:
                        print(
                            f"[SOLO_PLANNER_SSE] DB write failed: {e}", flush=True
                        )
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
                print(
                    f"[SOLO_PLANNER_SSE] Writer task raised on drain: {e}",
                    flush=True,
                )

            # Update terminal statuses.
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
                        else:
                            plan_row.status = PlanStatus.DRAFT
                            itin_row.status = TripItineraryStatus.PENDING
                        await db.commit()
            except Exception as e:
                print(
                    f"[SOLO_PLANNER_SSE] Failed to update final statuses: {e}",
                    flush=True,
                )

        try:
            async for chunk in generate_trip_itinerary(
                trip_payload,
                mode=mode,
                current_trip_itinerary=current_trip_itinerary,
                owner_id=str(user_id),
                trip_id=str(id),
                cancellation_callback=request.is_disconnected,
            ):
                chunk_type = chunk.get("type")

                # Forward first — never block the stream on DB work.
                yield f"data: {json.dumps(chunk)}\n\n"

                if chunk_type == "event":
                    event_data = chunk.get("data") or {}
                    if event_data:
                        await write_queue.put(event_data)
                elif chunk_type == "summary":
                    # Any summary text means the agent reached END and is
                    # finalizing. Mark success; more summary chunks may follow.
                    success = True
                elif chunk_type == "error":
                    success = False
                    break

        except asyncio.CancelledError:
            print(
                f"[SOLO_PLANNER_SSE] Client disconnected for trip {id} — finalizing.",
                flush=True,
            )
            # Fall through to the shielded finalize in the finally block.
            raise
        except Exception as e:
            print(
                f"[SOLO_PLANNER_SSE] Unexpected error while streaming: {e}",
                flush=True,
            )
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
                    print(
                        f"[SOLO_PLANNER_SSE] Finalize raised (will still complete in background): {e}",
                        flush=True,
                    )
                # Do NOT re-raise here; the outer except already handled
                # the original exception. The finally's job is just to
                # guarantee finalize was scheduled.

    return StreamingResponse(event_generator(), media_type="text/event-stream")
