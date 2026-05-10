"""Thin adapter to run editor graph and stream SSE chunks."""

import asyncio
import uuid
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional

from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.streaming import reset_stream_writer, set_stream_writer
from app.logging import get_agent_logger

log = get_agent_logger("editor_planner")


async def run_editor_chat(
    trip_id: str,
    user_message: str,
    user_id: str,
    chat_history: Optional[List[Dict]] = None,
    attached_events: Optional[List[Dict]] = None,
    cached_itinerary_events: Optional[List[Dict]] = None,
    cached_trip_input: Optional[Dict[str, Any]] = None,
    cached_research_facts: Optional[Dict[str, Any]] = None,
    base_snapshot_cursor: Optional[int] = None,
    base_events_hash: Optional[str] = None,
    force_reload_itinerary: bool = False,
    cancellation_callback: Optional[Callable[[], Awaitable[bool]]] = None,
    use_fast_model: bool = False,
) -> AsyncGenerator[Dict[str, Any], None]:
    from app.agent.langgraph_runtime.graph import get_editor_graph

    initial_state: EditorState = {
        "user_id": user_id,
        "trip_id": trip_id,
        "user_message": user_message,
        "chat_history": chat_history or [],
        "attached_events": attached_events or [],
        "cached_itinerary_events": cached_itinerary_events or [],
        "cached_trip_input": cached_trip_input or {},
        "cached_research_facts": cached_research_facts or {},
        "client_base_snapshot_cursor": base_snapshot_cursor,
        "client_base_events_hash": base_events_hash or "",
        "force_reload_itinerary": force_reload_itinerary,
        "cancelled": False,
        "use_fast_model": use_fast_model,
    }

    graph = get_editor_graph()
    run_id = str(uuid.uuid4())
    graph_config = {"configurable": {"thread_id": run_id}}

    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    def _writer(chunk: Dict[str, Any]) -> None:
        try:
            queue.put_nowait(chunk)
        except Exception:
            pass

    token = set_stream_writer(_writer)

    async def _run_graph() -> None:
        try:
            async for _ in graph.astream(initial_state, graph_config):
                pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("Unhandled runtime error in editor graph", error=str(exc))
            try:
                queue.put_nowait({"type": "error", "content": f"Runtime Error: {exc}"})
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
        async def _poll() -> None:
            while True:
                await asyncio.sleep(2)
                try:
                    if await cancellation_callback():
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
