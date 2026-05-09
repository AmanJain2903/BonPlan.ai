from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.agent.core import runtime as runtime_module


@pytest.mark.anyio
async def test_open_remote_mcp_session_with_retry_retries_until_success(monkeypatch):
    attempts = 0
    sleep_calls: list[float] = []
    clock = {"now": 0.0}

    @asynccontextmanager
    async def _fake_open_remote_mcp_session():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError(f"not ready {attempts}")
        yield "session", "response"

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock["now"] += seconds

    class _FakeLoop:
        def time(self) -> float:
            return clock["now"]

    monkeypatch.setattr(runtime_module, "_open_remote_mcp_session", _fake_open_remote_mcp_session)
    monkeypatch.setattr(runtime_module.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(runtime_module.asyncio, "get_running_loop", lambda: _FakeLoop())
    monkeypatch.setattr(runtime_module.settings, "MCP_STARTUP_MAX_WAIT_SECONDS", 10.0)
    monkeypatch.setattr(runtime_module.settings, "MCP_STARTUP_INITIAL_BACKOFF_SECONDS", 1.0)
    monkeypatch.setattr(runtime_module.settings, "MCP_STARTUP_MAX_BACKOFF_SECONDS", 5.0)

    async with runtime_module._open_remote_mcp_session_with_retry() as result:
        assert result == ("session", "response")

    assert attempts == 3
    assert sleep_calls == [1.0, 2.0]


@pytest.mark.anyio
async def test_open_remote_mcp_session_with_retry_raises_after_budget_exhausted(monkeypatch):
    sleep_calls: list[float] = []
    clock = {"now": 0.0}

    @asynccontextmanager
    async def _always_fail_open_remote_mcp_session():
        raise RuntimeError("still unavailable")
        yield

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        clock["now"] += seconds

    class _FakeLoop:
        def time(self) -> float:
            return clock["now"]

    monkeypatch.setattr(runtime_module, "_open_remote_mcp_session", _always_fail_open_remote_mcp_session)
    monkeypatch.setattr(runtime_module.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(runtime_module.asyncio, "get_running_loop", lambda: _FakeLoop())
    monkeypatch.setattr(runtime_module.settings, "MCP_STARTUP_MAX_WAIT_SECONDS", 3.0)
    monkeypatch.setattr(runtime_module.settings, "MCP_STARTUP_INITIAL_BACKOFF_SECONDS", 1.0)
    monkeypatch.setattr(runtime_module.settings, "MCP_STARTUP_MAX_BACKOFF_SECONDS", 10.0)

    with pytest.raises(RuntimeError, match="still unavailable"):
        async with runtime_module._open_remote_mcp_session_with_retry():
            pass

    assert sleep_calls == [1.0, 2.0]
