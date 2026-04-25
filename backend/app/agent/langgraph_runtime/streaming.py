"""
ContextVar-backed streaming writer for LangGraph nodes.

LangGraph's built-in `get_stream_writer()` relies on contextvar propagation
that is broken on Python < 3.11 under asyncio (documented upstream). We run on
Python 3.10, so we publish our own writer through a ContextVar that we set in
the outer generator (`generate_trip_itinerary`) *before* `graph.astream(...)`
is awaited. Because `asyncio.create_task` copies the current context, every
sub-task LangGraph spawns inherits the writer and `emit(...)` works inside
nodes without relying on LangGraph internals.

Usage:
    writer_ctx_token = set_stream_writer(some_callable)
    try:
        async for _ in graph.astream(...):
            ...
    finally:
        reset_stream_writer(writer_ctx_token)

Outside of a configured context `emit(...)` is a silent no-op so tests that
construct nodes directly don't blow up.
"""
from contextvars import ContextVar, Token
from typing import Any, Callable, Dict, Optional

from app.logging import get_agent_logger

logger = get_agent_logger("langgraph_runtime.streaming")

StreamWriter = Callable[[Dict[str, Any]], None]

_stream_writer: ContextVar[Optional[StreamWriter]] = ContextVar(
    "bonplan_stream_writer", default=None
)


def set_stream_writer(writer: StreamWriter) -> Token:
    """Install a writer for the current (and child) async contexts."""
    return _stream_writer.set(writer)


def reset_stream_writer(token: Token) -> None:
    # Async generators re-enter their body in a different context copy on
    # each `asend(...)`, which makes Token-based reset unreliable — the token
    # is context-scoped. If reset() fails we just unset the writer directly;
    # when the generator task ends its context is discarded anyway.
    try:
        _stream_writer.reset(token)
    except (ValueError, LookupError):
        logger.warning("Failed to reset stream writer. Unsetting the writer directly.")
        try:
            _stream_writer.set(None)
        except Exception:
            logger.error("Failed to unset stream writer.")
            pass


def emit(chunk: Dict[str, Any]) -> None:
    writer = _stream_writer.get()
    if writer is None:
        logger.error("Stream writer not found.")
        return
    writer(chunk)
