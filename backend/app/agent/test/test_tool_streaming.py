from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.editing import engine
from app.agent.langgraph_runtime.nodes import conversational
from app.agent.langgraph_runtime.streaming import reset_stream_writer, set_stream_writer
from app.agent.llm import litellm_types as types


class _NoopRateLimiter:
    async def consume(self, _sku):
        return None


class _FakeMcpSession:
    def __init__(self, responses: dict[str, str]):
        self.responses = responses

    async def call_tool(self, name: str, args: dict):
        payload = self.responses[name]
        return SimpleNamespace(content=[SimpleNamespace(text=payload)])


class _FakeChat:
    def __init__(self, streams: list[list[types.StreamChunk]]):
        self._streams = streams
        self._idx = 0

    def send_message_stream(self, _message):
        chunks = self._streams[self._idx]
        self._idx += 1

        async def _gen():
            for chunk in chunks:
                yield chunk

        return _gen()


class _FakeModelClient:
    def __init__(self, chat: _FakeChat):
        self.aio = SimpleNamespace(
            chats=SimpleNamespace(create=lambda **_: chat),
        )


def _stream_chunks_for_tool_call() -> list[list[types.StreamChunk]]:
    return [
        [
            types.StreamChunk(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="assistant",
                            parts=[
                                types.Part(
                                    function_call=types.FunctionCall(
                                        name="search_places",
                                        args={"query": "coffee"},
                                        id="call_1",
                                    )
                                )
                            ],
                        ),
                        finish_reason="",
                    )
                ]
            )
        ],
        [
            types.StreamChunk(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="assistant",
                            parts=[types.Part(text="Found a good coffee stop.")],
                        ),
                        finish_reason="STOP",
                    )
                ]
            )
        ],
    ]


@pytest.mark.anyio
async def test_conversational_node_emits_tool_chunks(monkeypatch):
    emitted: list[dict] = []
    token = set_stream_writer(emitted.append)
    chat = _FakeChat(_stream_chunks_for_tool_call())

    monkeypatch.setattr(conversational, "get_rate_limiter", lambda: _NoopRateLimiter())
    monkeypatch.setattr(runtime, "model_client", _FakeModelClient(chat))
    monkeypatch.setattr(runtime, "mcp_session", _FakeMcpSession({"search_places": json.dumps({"place": {"name": "Blue Bottle"}})}))

    try:
        result = await conversational.conversational_node(
            {
                "conversation_notes": "",
                "is_structural_change": False,
                "user_message": "Find me coffee nearby",
                "current_itinerary_events": [],
                "attached_events": [],
                "chat_history": [],
            }
        )
    finally:
        reset_stream_writer(token)

    assert result == {}
    assert [chunk["type"] for chunk in emitted] == [
        "tool_call",
        "summary",
        "conversation_end",
    ]
    assert emitted[0]["tool_name"] == "search_places"
    assert emitted[0]["args"] == {"query": "coffee"}
    assert emitted[0]["call_id"] == "call_1"


@pytest.mark.anyio
async def test_search_place_emits_tool_chunks(monkeypatch):
    emitted: list[dict] = []
    token = set_stream_writer(emitted.append)

    monkeypatch.setattr(
        runtime,
        "mcp_session",
        _FakeMcpSession(
            {
                "search_places": json.dumps(
                    {
                        "place": {
                            "name": "Blue Bottle",
                            "type": "cafe",
                            "location": {"latitude": 37.78, "longitude": -122.4},
                        }
                    }
                )
            }
        ),
    )

    try:
        place = await engine._search_place("coffee")
    finally:
        reset_stream_writer(token)

    assert place == {
        "name": "Blue Bottle",
        "type": "cafe",
        "location": {"latitude": 37.78, "longitude": -122.4},
    }
    assert [chunk["type"] for chunk in emitted] == ["tool_call"]
    assert emitted[0]["tool_name"] == "search_places"
    assert emitted[0]["args"]["query"] == "coffee"
