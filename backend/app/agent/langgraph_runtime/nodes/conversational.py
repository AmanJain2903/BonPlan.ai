"""Conversational node for itinerary assistant (read-only)."""

import json
import os
import re
from typing import Any, Dict

from app.agent.llm import litellm_types as types
from app.agent.core.runtime import _DAY_MCP_TOOLS, _RESEARCH_MCP_TOOLS, runtime
from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.streaming import emit
from app.core.config import settings
from app.logging import get_agent_logger
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_llm_model_sku

log = get_agent_logger("conversational_node")
CONVERSATION_MODEL_SKU = resolve_llm_model_sku(settings.CONVERSATION_AGENT_MODEL)

_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "editor", "conversationalPrompt.md"
)
with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    CONVERSATIONAL_SYSTEM_PROMPT = _f.read()


_NEW_TRIP_RE = re.compile(
    r"\b("
    r"new\s+(trip|itinerary|plan)"
    r"|another\s+(trip|itinerary|plan)"
    r"|different\s+(trip|itinerary|plan)"
    r"|plan\s+(me\s+)?a\s+(trip|itinerary)"
    r"|start\s+(a\s+)?(new\s+)?(trip|itinerary|plan)"
    r"|create\s+(a\s+)?(new\s+)?(trip|itinerary|plan)"
    r")\b",
    re.IGNORECASE,
)


def _compact_itinerary(events: list[dict]) -> list[dict]:
    out = []
    for e in events or []:
        item = {
            "day_number": e.get("day_number"),
            "event_number": e.get("event_number"),
            "event_type": e.get("event_type"),
            "day_title": e.get("day_title"),
            "date": e.get("date"),
        }
        for field in (
            "place_details",
            "commute_details",
            "hotel_checkin_details",
            "hotel_checkout_details",
            "flight_takeoff_details",
            "flight_land_details",
            "car_pickup_details",
            "car_dropoff_details",
            "other_details",
        ):
            if e.get(field):
                item[field] = e.get(field)
                break
        out.append(item)
    return out


def _truncate_tool_output(text: str, cap: int = 8000) -> str:
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n…[truncated, {len(text) - cap} chars dropped]"


async def conversational_node(state: EditorState) -> Dict[str, Any]:
    conversation_notes = state.get("conversation_notes", "")
    if state.get("is_structural_change") and conversation_notes:
        emit({"type": "summary", "content": conversation_notes})
        emit({"type": "conversation_end"})
        return {}

    if _NEW_TRIP_RE.search(state.get("user_message", "") or ""):
        emit(
            {
                "type": "summary",
                "content": (
                    "I can only answer questions about this current itinerary or make event-level edits to it. "
                    "I cannot create or start a new trip from this chat."
                ),
            }
        )
        emit({"type": "conversation_end"})
        return {}

    if runtime.mcp_session is None or runtime.model_client is None:
        emit({"type": "error", "content": "Agent runtime not ready."})
        return {"cancelled": True}

    allowed = set(_RESEARCH_MCP_TOOLS) | set(_DAY_MCP_TOOLS)
    mcp_decls = [
        d for d in (runtime.llm_tools or [])
        if d.name in allowed and d.name != "add_itinerary_event"
    ]
    tool_block = types.Tool(function_declarations=mcp_decls)

    config = types.GenerateContentConfig(
        tools=[tool_block],
        system_instruction=CONVERSATIONAL_SYSTEM_PROMPT,
        temperature=0.4,
        max_output_tokens=4096,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    CURRENT_ITINERARY = json.dumps(_compact_itinerary(state.get('current_itinerary_events') or []), default=str)
    if CURRENT_ITINERARY:
        CURRENT_ITINERARY = f"CURRENT ITINERARY:\n{CURRENT_ITINERARY}\n\n"
    ATTACHED_EVENTS = json.dumps(state.get('attached_events') or [], default=str)
    if ATTACHED_EVENTS:
        ATTACHED_EVENTS = f"ATTACHED EVENTS:\n{ATTACHED_EVENTS}\n\n"
    CHAT_HISTORY = json.dumps(state.get('chat_history') or [], default=str)
    if CHAT_HISTORY:
        CHAT_HISTORY = f"CHAT HISTORY:\n{CHAT_HISTORY}\n\n"
    initial_message = (
        f"{conversation_notes}\n\n"
        f"{CHAT_HISTORY}"
        f"{CURRENT_ITINERARY}"
        f"{ATTACHED_EVENTS}"
        "Use CHAT HISTORY to resolve references like this/that/there before answering.\n\n"
        f"USER QUESTION: {state.get('user_message', '')}\n\n"
    )

    client = runtime.model_client
    chat = client.aio.chats.create(model=settings.CONVERSATION_AGENT_MODEL, config=config)
    current_message: Any = initial_message

    max_turns = 24
    for _turn in range(max_turns):
        try:
            await get_rate_limiter().consume(CONVERSATION_MODEL_SKU)
        except RateLimitExceeded as exc:
            emit({"type": "error", "content": f"Conversation quota exhausted. Retry after {exc.retry_after_seconds}s."})
            return {"cancelled": True}

        try:
            response_stream = chat.send_message_stream(current_message)
        except Exception as exc:
            emit({"type": "error", "content": f"Conversation model error: {exc}"})
            return {"cancelled": True}

        finish_reason = ""
        tool_calls: list[types.FunctionCall] = []
        pending_turn_text = ""

        try:
            async for chunk in response_stream:
                if chunk.candidates:
                    try:
                        finish_reason = str(chunk.candidates[0].finish_reason or "")
                    except Exception:
                        finish_reason = ""

                parts = (
                    chunk.candidates[0].content.parts
                    if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts
                    else []
                )

                for part in parts:
                    if isinstance(part.text, str) and part.text:
                        is_thought = bool(getattr(part, "thought", False))
                        if is_thought:
                            emit({"type": "thinking", "content": part.text})
                        else:
                            pending_turn_text += part.text
                    if part.function_call:
                        tool_calls.append(part.function_call)
        except Exception as exc:
            log.error("Conversation stream error", error=str(exc))
            emit({"type": "error", "content": f"Conversation model error: {exc}"})
            return {"cancelled": True}

        if not tool_calls:
            finish_upper = finish_reason.upper()
            final_text = pending_turn_text.strip()
            if final_text:
                # Final non-thought answer.
                emit({"type": "summary", "content": final_text})
            if "STOP" in finish_upper:
                emit({"type": "conversation_end"})
                return {}
            if "MAX_TOKENS" in finish_upper or "MALFORMED" in finish_upper:
                emit({"type": "error", "content": f"Conversation halted: {finish_reason}"})
                return {"cancelled": True}
            continue

        tool_responses = []
        for fc in tool_calls:
            if fc.name.startswith("add_") or fc.name == "add_itinerary_event":
                tool_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"error": "Itinerary mutation tools are disabled in conversational mode."},
                        tool_call_id=fc.id,
                    )
                )
                continue

            try:
                mcp_result = await runtime.mcp_session.call_tool(fc.name, dict(fc.args or {}))
                output = "".join(c.text for c in mcp_result.content if hasattr(c, "text")) or "Task completed."
                output = _truncate_tool_output(output)
                tool_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"output": output},
                        tool_call_id=fc.id,
                    )
                )
            except Exception as exc:
                tool_responses.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"error": str(exc)},
                        tool_call_id=fc.id,
                    )
                )

        current_message = tool_responses

    emit({"type": "error", "content": "Conversation exceeded turn budget."})
    return {"cancelled": True}
