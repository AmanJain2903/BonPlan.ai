"""
Unit tests for MCP session reconnect logic (runtime.py).

Covers tests 3 and 4 from the manual test plan:
  3a. attempt_mcp_reconnect() swaps session + marks mcp_healthy=True
  3b. attempt_mcp_reconnect() closes the previous _reconnect_stack
  3c. attempt_mcp_reconnect() returns False (never raises) when server is down
  4.  Concurrent attempt_mcp_reconnect() calls are serialized by the lock
"""
import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from app.agent.core.runtime import attempt_mcp_reconnect


def run(coro):
    return asyncio.run(coro)


def _reset_runtime():
    """Reset the shared runtime singleton to a clean slate between tests."""
    from app.agent.core.runtime import runtime
    runtime.mcp_session = None
    runtime.mcp_healthy = False
    runtime._reconnect_stack = None
    # Set to None so the next test's asyncio.run() gets a fresh lock bound to
    # that run's event loop — avoids "Future attached to a different loop" errors.
    runtime._reconnect_lock = None


def _open_factory(session, response):
    """
    Returns a side_effect callable for patching _open_remote_mcp_session.
    Each call returns a fresh async context manager that yields (session, response).
    """
    def _make():
        @asynccontextmanager
        async def _ctx():
            yield session, response
        return _ctx()
    return _make


# ── 3a: session swap ──────────────────────────────────────────────────────────

def test_reconnect_calls_rebuild_with_new_session_and_marks_healthy():
    """attempt_mcp_reconnect() passes the new session to _rebuild and sets mcp_healthy=True."""
    _reset_runtime()
    new_session = AsyncMock()
    new_response = MagicMock(tools=[])

    with patch(
        "app.agent.core.runtime._open_remote_mcp_session",
        side_effect=_open_factory(new_session, new_response),
    ) as mock_open, patch(
        "app.agent.core.runtime._rebuild_runtime_from_session"
    ) as mock_rebuild:
        result = run(attempt_mcp_reconnect())

    assert result is True
    mock_open.assert_called_once()
    mock_rebuild.assert_called_once_with(new_session, new_response)

    from app.agent.core.runtime import runtime
    assert runtime.mcp_healthy is True
    assert runtime._reconnect_stack is not None  # new stack is stored


# ── 3b: old stack cleanup ─────────────────────────────────────────────────────

def test_reconnect_closes_previous_reconnect_stack():
    """attempt_mcp_reconnect() calls aclose() on the previous _reconnect_stack."""
    _reset_runtime()
    from app.agent.core.runtime import runtime

    old_stack = MagicMock()
    old_stack.aclose = AsyncMock()
    runtime._reconnect_stack = old_stack

    new_session = AsyncMock()
    new_response = MagicMock(tools=[])

    with patch(
        "app.agent.core.runtime._open_remote_mcp_session",
        side_effect=_open_factory(new_session, new_response),
    ), patch("app.agent.core.runtime._rebuild_runtime_from_session"):
        result = run(attempt_mcp_reconnect())

    assert result is True
    old_stack.aclose.assert_awaited_once()


def test_reconnect_no_crash_when_old_stack_aclose_raises():
    """attempt_mcp_reconnect() succeeds even if the old stack's aclose() throws."""
    _reset_runtime()
    from app.agent.core.runtime import runtime

    old_stack = MagicMock()
    old_stack.aclose = AsyncMock(side_effect=RuntimeError("already closed"))
    runtime._reconnect_stack = old_stack

    new_session = AsyncMock()
    new_response = MagicMock(tools=[])

    with patch(
        "app.agent.core.runtime._open_remote_mcp_session",
        side_effect=_open_factory(new_session, new_response),
    ), patch("app.agent.core.runtime._rebuild_runtime_from_session"):
        result = run(attempt_mcp_reconnect())

    assert result is True
    assert runtime.mcp_healthy is True


# ── 3c: server unreachable ────────────────────────────────────────────────────

def test_reconnect_returns_false_when_mcp_unreachable():
    """attempt_mcp_reconnect() returns False (never raises) when the server is down."""
    _reset_runtime()

    def _failing():
        @asynccontextmanager
        async def _ctx():
            raise ConnectionRefusedError("MCP down")
            yield  # pragma: no cover
        return _ctx()

    with patch("app.agent.core.runtime._open_remote_mcp_session", side_effect=_failing):
        result = run(attempt_mcp_reconnect())

    assert result is False
    from app.agent.core.runtime import runtime
    assert runtime.mcp_healthy is False  # unchanged — we didn't reconnect


def test_reconnect_leaves_no_partial_stack_on_failure():
    """_reconnect_stack stays None when the reconnect attempt fails."""
    _reset_runtime()

    def _failing():
        @asynccontextmanager
        async def _ctx():
            raise OSError("network gone")
            yield  # pragma: no cover
        return _ctx()

    with patch("app.agent.core.runtime._open_remote_mcp_session", side_effect=_failing):
        run(attempt_mcp_reconnect())

    from app.agent.core.runtime import runtime
    assert runtime._reconnect_stack is None


# ── 4: concurrent calls are serialized ───────────────────────────────────────

def test_concurrent_reconnects_are_serialized_by_lock():
    """
    Three simultaneous attempt_mcp_reconnect() calls must not interleave.

    The lock ensures no two tasks are inside the reconnect critical section at
    the same time.  We verify this by checking that every "enter" is immediately
    followed by its own "yield" — no other "enter" sneaks in between.

    Note: "exit" (code after `yield` in the ctx manager) is triggered when the
    *next* reconnect closes the old stack via aclose(), so exits appear later in
    the sequence and are not part of the serialization assertion.
    """
    _reset_runtime()
    call_order = []

    def _tracked_factory():
        @asynccontextmanager
        async def _ctx():
            call_order.append("enter")
            await asyncio.sleep(0)  # relinquish control — concurrent tasks race here
            call_order.append("yield")
            yield AsyncMock(), MagicMock(tools=[])
            call_order.append("exit")
        return _ctx()

    async def _gather():
        with patch(
            "app.agent.core.runtime._open_remote_mcp_session",
            side_effect=_tracked_factory,
        ), patch("app.agent.core.runtime._rebuild_runtime_from_session"):
            return await asyncio.gather(
                attempt_mcp_reconnect(),
                attempt_mcp_reconnect(),
                attempt_mcp_reconnect(),
            )

    results = run(_gather())

    assert all(r is True for r in results)

    # Every "enter" must be immediately followed by "yield" — proves no two tasks
    # were inside the lock at the same time.
    # Without lock: ["enter","enter","enter","yield","yield","yield",...]
    # With lock:    ["enter","yield",...,"enter","yield",...,"enter","yield",...]
    for i, event in enumerate(call_order):
        if event == "enter":
            assert i + 1 < len(call_order) and call_order[i + 1] == "yield", (
                f"'enter' at index {i} not immediately followed by 'yield' — "
                f"lock is not serializing reconnects. Full order: {call_order}"
            )
    # All three reconnects happened
    assert call_order.count("enter") == 3


def test_concurrent_reconnects_all_succeed_even_if_serialized():
    """All concurrent callers get True — the lock doesn't cause any to fail."""
    _reset_runtime()

    def _factory():
        @asynccontextmanager
        async def _ctx():
            yield AsyncMock(), MagicMock(tools=[])
        return _ctx()

    async def _gather():
        with patch(
            "app.agent.core.runtime._open_remote_mcp_session",
            side_effect=_factory,
        ), patch("app.agent.core.runtime._rebuild_runtime_from_session"):
            return await asyncio.gather(*[attempt_mcp_reconnect() for _ in range(5)])

    results = run(_gather())
    assert results == [True] * 5
