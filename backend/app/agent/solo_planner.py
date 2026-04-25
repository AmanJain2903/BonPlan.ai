# backend/app/agent/solo_planner.py

# Mock Agent Function
# import os
# import os
# import json
# from typing import AsyncGenerator, Dict, Any, Literal, Optional, Callable, Awaitable
# import asyncio

# relativePath = os.path.join(os.path.dirname(__file__), "mock_data")
# absolutePath = os.path.abspath(relativePath)
# mock_file_path = os.path.join(absolutePath, "mock_chunk_18_04_2026.json")
# baseDelay = 0.2 # in seconds

# delaysForChunks = {
#     "thinking": baseDelay,
#     "summary": baseDelay*1.1,
#     "tool_call": baseDelay*1.5,
#     "tool_response": baseDelay*2,
#     "event": baseDelay*2.5,
#     "system": baseDelay,
#     "error": baseDelay
# }

# async def generate_trip_itinerary(trip_payload: dict, mode: Literal["autonomous", "collaborative", "editing"] = "autonomous", current_trip_itinerary: Optional[list] = None, owner_id: Optional[str] = None, trip_id: Optional[str] = None, cancellation_callback: Optional[Callable[[], Awaitable[bool]]] = None) -> AsyncGenerator[Dict[str, Any], None]:

#     async def check_cancellation():
#         if cancellation_callback and await cancellation_callback():
#             return True
#         return False
    
#     if await check_cancellation():
#         return

#     with open(mock_file_path, "r") as f:
#         mock_chunks = json.load(f)
    
#     last_chunk = mock_chunks[-1]    
#     for chunk in mock_chunks[:-1]:
#         await asyncio.sleep(delaysForChunks[chunk["type"]])
#         yield chunk
#     await asyncio.sleep(5)
#     yield last_chunk

from typing import AsyncGenerator, Dict, Any, Literal, Optional, Callable, Awaitable, List
import asyncio
import uuid

from app.logging import get_agent_logger
from app.agent.schemas.structuredOutput import AddItineraryEvent

log = get_agent_logger("solo_planner")


async def generate_trip_itinerary(
    trip_payload: dict,
    current_trip_itinerary: Optional[list] = None,
    mode: Literal["autonomous", "collaborative", "editing"] = "autonomous",
    owner_id: Optional[str] = None,
    trip_id: Optional[str] = None,
    cancellation_callback: Optional[Callable[[], Awaitable[bool]]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Thin LangGraph adapter.  All planning logic lives in langgraph_runtime/.

    Cancellation: if `cancellation_callback` is provided a background task polls
    it every 2 s and cancels the main task on True, which propagates as
    asyncio.CancelledError through the generator.
    """
    from app.agent.langgraph_runtime.graph import get_planner_graph
    from app.agent.langgraph_runtime.streaming import (
        set_stream_writer,
        reset_stream_writer,
    )

    log.info("Starting generation", trip_id=trip_id, mode=mode)

    # Derive resume point from previously emitted events.
    current_day = 0
    next_event_number = 1
    is_resuming = False
    sanitized_prior_events: list = []
    if current_trip_itinerary:
        per_day_max: Dict[int, int] = {}
        max_positive_day = 0
        for raw in current_trip_itinerary:
            try:
                evt = AddItineraryEvent(**raw)
                d = evt.model_dump()
                sanitized_prior_events.append(d)
                day = d.get("day_number", 0)
                evnum = d.get("event_number", 0)
                if isinstance(day, int) and day > 0:
                    max_positive_day = max(max_positive_day, day)
                    if isinstance(evnum, int):
                        per_day_max[day] = max(per_day_max.get(day, 0), evnum)
            except Exception as e:
                log.error("Resume Point Derivation Failed.", error=str(e))
                return
        if sanitized_prior_events:
            is_resuming = True
        if max_positive_day > 0:
            current_day = max_positive_day
            next_event_number = per_day_max.get(max_positive_day, 0) + 1
        # START was emitted but no numbered day yet — resume at day 1.
        elif is_resuming:
            current_day = 1
            next_event_number = 1

    initial_state = {
        "trip_input": trip_payload,
        "mode": mode,
        "owner_id": owner_id,
        "trip_id": trip_id,
        "current_day": current_day,
        "next_event_number": next_event_number,
        "is_resuming": is_resuming,
        "prior_events": sanitized_prior_events,
        "cancelled": False,
        "is_complete": False,
        "phase": "bootstrap",
    }

    run_id = str(uuid.uuid4())
    graph_config = {"configurable": {"thread_id": run_id}}

    graph = get_planner_graph()

    # Queue-backed writer.
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def _writer(chunk: Dict[str, Any]) -> None:
        try:
            queue.put_nowait(chunk)
        except Exception as put_err:
            log.warning("Queue put failed", error=str(put_err))

    token = set_stream_writer(_writer)

    async def _run_graph() -> None:
        try:
            async for _ in graph.astream(initial_state, graph_config):
                pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            log.error("Unhandled runtime error in graph task", error=str(e))
            try:
                queue.put_nowait({"type": "error", "content": f"Runtime Error: {e}"})
            except Exception:
                pass
        finally:
            try:
                queue.put_nowait(_SENTINEL)
            except Exception:
                pass

    graph_task = asyncio.create_task(_run_graph())

    cancel_poll_task: Optional[asyncio.Task] = None
    if cancellation_callback:
        async def _poll():
            while True:
                await asyncio.sleep(2)
                try:
                    if await cancellation_callback():
                        log.info("Cancellation callback triggered", trip_id=trip_id)
                        graph_task.cancel()
                        return
                except Exception:
                    pass
        cancel_poll_task = asyncio.create_task(_poll())

    try:
        while True:
            chunk = await queue.get()
            if chunk is _SENTINEL:
                break
            yield chunk
    except asyncio.CancelledError:
        log.info("Generator cancelled", trip_id=trip_id)
        graph_task.cancel()
        raise
    finally:
        reset_stream_writer(token)
        if cancel_poll_task and not cancel_poll_task.done():
            cancel_poll_task.cancel()
        if not graph_task.done():
            graph_task.cancel()
        try:
            await graph_task
        except (asyncio.CancelledError, Exception):
            pass

    return
