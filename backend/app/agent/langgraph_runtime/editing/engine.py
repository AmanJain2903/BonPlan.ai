"""Candidate-first itinerary editing engine."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Optional

from app.agent.core.runtime import runtime
from app.agent.helpers.itinerary_event_cost import sum_chargeable_cost_usd
from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.output_style import with_user_facing_output_policy
from app.agent.langgraph_runtime.streaming import emit
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.agent.llm import litellm_types as types
from app.core.config import settings
from app.database.database import Session
from app.logging import get_agent_logger
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_llm_model_sku

from .event_utils import (
    BOOKING_PAIR_TYPES,
    FLEXIBLE_TIMED_TYPES,
    SORT_STEP,
    canonicalize_events,
    compact_itinerary_for_prompt,
    date_for_day,
    day_boundaries,
    day_sort_key,
    day_title,
    detail_field_for_event,
    event_by_id,
    event_by_legacy_ref,
    event_description,
    event_duration_minutes,
    event_end,
    event_location_name,
    event_name,
    event_origin_dest,
    event_start,
    events_hash,
    events_same_location,
    finite_float,
    format_dt,
    group_members,
    is_fixed_time_event,
    is_flexible_timed_event,
    is_locked,
    next_legacy_event_number,
    normalize_text,
    parse_dt,
    regular_events,
    remove_event_ids,
    replace_event_by_id,
    set_event_window,
    sort_key_between,
)
from .full_validator import validate_candidate
from .snapshot_service import CommitResult, EditConflictError, commit_candidate


log = get_agent_logger("itinerary_editor")
EDITOR_MODEL_SKU = resolve_llm_model_sku(settings.EDITOR_AGENT_MODEL)

_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "editor", "editPlannerPrompt.md"
)
with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    EDIT_PLANNER_PROMPT = _f.read()


@dataclass
class EditOutcome:
    status: str
    summary: str = ""
    question: str = ""
    reason: str = ""
    commit: Optional[CommitResult] = None
    validation_errors: list[str] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)


class EditRejected(RuntimeError):
    pass


class EditClarification(RuntimeError):
    pass


_CLARIFICATION_MARKERS = (
    "can you clarify",
    "which event",
    "which single event",
    "which trip day",
    "which day",
    "what time",
    "which one",
    "which place",
    "which reference",
    "should i edit",
    "should i place",
)

_TOOL_RESPONSE_CAPS: dict[str, int] = {
    "search_hotels": 12000,
    "search_places": 8000,
    "search_places_nearby": 8000,
    "search_flights": 12000,
    "search_multi_city_flights": 12000,
    "get_next_flights": 12000,
    "search_rental_cars": 12000,
    "search_web": 6000,
    "get_content_from_url": 5000,
    "get_place_info": 8000,
}
_DEFAULT_TOOL_RESPONSE_CAP = 8000
_MAX_EDITOR_MCP_TOOL_CALLS = 3
_NEARBY_SEARCH_RADIUS_M = 4_000.0
_RELATIVE_PLACE_MAX_DISTANCE_M = 15_000.0


def _extract_json(text: Any) -> Optional[dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _truncate_tool_output(text: str, tool_name: str) -> str:
    cap = _TOOL_RESPONSE_CAPS.get(tool_name, _DEFAULT_TOOL_RESPONSE_CAP)
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n...[truncated, {len(text) - cap} chars dropped]"


def _available_editor_tool_names() -> set[str]:
    tool_block = runtime.editor_tool_block
    if tool_block is None:
        return set()
    return {
        decl.name
        for decl in tool_block.function_declarations
        if decl.name and decl.name != "add_itinerary_event" and not decl.name.startswith("add_")
    }


async def _execute_editor_tool(fc: types.FunctionCall, allowed_tool_names: set[str]) -> types.Part:
    call_id = fc.id or f"call_{uuid.uuid4().hex}"
    tool_name = fc.name
    if runtime.mcp_session is None:
        result = {"error": "MCP runtime is not available."}
    elif tool_name not in allowed_tool_names:
        result = {"error": f"Tool '{tool_name}' is not available to the itinerary editor."}
    else:
        args = dict(fc.args or {})
        emit({"type": "tool_call", "tool_name": tool_name, "args": args, "call_id": call_id})
        try:
            timeout = TIMEOUTS.get(tool_name, 60)
            mcp_result = await asyncio.wait_for(
                runtime.mcp_session.call_tool(tool_name, args),
                timeout=timeout,
            )
            output = "".join(c.text for c in mcp_result.content if hasattr(c, "text")) or "Task completed."
            output = _truncate_tool_output(output, tool_name)
            result = {"output": output}
        except asyncio.TimeoutError:
            result = {
                "error": (
                    f"Tool '{tool_name}' timed out. Do not retry it for this edit; "
                    "continue with the best safe edit plan."
                )
            }
        except Exception as exc:
            result = {"error": str(exc)}
    return types.Part.from_function_response(
        name=tool_name,
        response=result,
        tool_call_id=call_id,
    )


def _last_clarified_edit_message(user_message: str, chat_history: list) -> str:
    """Combine a user's answer with the edit request that triggered a clarification."""
    if not chat_history:
        return user_message

    last_assistant_idx: Optional[int] = None
    for idx in range(len(chat_history) - 1, -1, -1):
        item = chat_history[idx] if isinstance(chat_history[idx], dict) else {}
        if item.get("role") != "assistant":
            continue
        content = str(item.get("content") or "").lower()
        if "?" in content and any(marker in content for marker in _CLARIFICATION_MARKERS):
            last_assistant_idx = idx
            break

    if last_assistant_idx is None:
        return user_message

    previous_user = ""
    for idx in range(last_assistant_idx - 1, -1, -1):
        item = chat_history[idx] if isinstance(chat_history[idx], dict) else {}
        if item.get("role") == "user" and str(item.get("content") or "").strip():
            previous_user = str(item["content"]).strip()
            break

    if not previous_user:
        return user_message
    return f"{previous_user}\nClarification answer: {user_message.strip()}"


def _attached_summary(attached_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in attached_events or []:
        event = item.get("event_data") if isinstance(item, dict) else None
        if isinstance(event, dict):
            out.append({
                "day_number": event.get("day_number"),
                "event_number": event.get("event_number"),
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "is_locked": event.get("is_locked") is True,
                "name": event_name(event),
            })
        elif isinstance(item, dict):
            out.append({
                "day_number": item.get("day_number"),
                "event_number": item.get("event_number"),
                "event_id": item.get("event_id"),
            })
    return out


async def _llm_edit_plan(
    *,
    user_message: str,
    chat_history: list,
    events: list[dict[str, Any]],
    attached_events: list[dict[str, Any]],
    trip_input: dict[str, Any],
    use_fast_model: bool = False,
) -> Optional[dict[str, Any]]:
    if runtime.model_client is None:
        return None

    _edit_model, _ = settings.get_editor_agent_model(use_fast_model)
    _edit_sku = resolve_llm_model_sku(_edit_model)

    prompt_body = {
        "user_message": user_message,
        "chat_history": list(chat_history or [])[-8:],
        "attached_events": _attached_summary(attached_events),
        "itinerary": compact_itinerary_for_prompt(events),
        "trip_input": {
            "origin": trip_input.get("origin"),
            "destinations": trip_input.get("destinations"),
            "start_date": trip_input.get("start_date"),
            "end_date": trip_input.get("end_date"),
            "pace": trip_input.get("pace"),
            "budget": trip_input.get("budget"),
        },
    }

    tool_block = runtime.editor_tool_block if runtime.mcp_session is not None else None
    allowed_tool_names = _available_editor_tool_names() if tool_block is not None else set()
    if tool_block is not None and not allowed_tool_names:
        tool_block = None

    if tool_block is not None:
        try:
            client = runtime.model_client
            chat = client.aio.chats.create(
                model=_edit_model,
                config=with_user_facing_output_policy(
                    types.GenerateContentConfig(
                        tools=[tool_block],
                        system_instruction=EDIT_PLANNER_PROMPT,
                        temperature=0.1,
                        max_output_tokens=1800,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    )
                ),
            )
            current_message: Any = json.dumps(prompt_body, default=str)
            last_text = ""
            tool_calls_used = 0
            for _turn in range(6):
                await get_rate_limiter().consume(_edit_sku)
                response_stream = chat.send_message_stream(current_message)
                pending_text = ""
                tool_calls: list[types.FunctionCall] = []

                async for chunk in response_stream:
                    parts = (
                        chunk.candidates[0].content.parts
                        if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts
                        else []
                    )
                    for part in parts:
                        if isinstance(part.text, str) and part.text:
                            if not getattr(part, "thought", False):
                                pending_text += part.text
                        if part.function_call:
                            tool_calls.append(part.function_call)

                if pending_text.strip():
                    last_text = pending_text
                if not tool_calls:
                    parsed = _extract_json(last_text)
                    if parsed:
                        return parsed
                    return None

                tool_responses: list[types.Part] = []
                for fc in tool_calls:
                    call_id = fc.id or f"call_{uuid.uuid4().hex}"
                    if tool_calls_used >= _MAX_EDITOR_MCP_TOOL_CALLS:
                        tool_responses.append(
                            types.Part.from_function_response(
                                name=fc.name,
                                response={
                                    "error": (
                                        "Editor MCP tool budget exhausted for this request. "
                                        "Return the safest JSON edit plan now without more tools."
                                    )
                                },
                                tool_call_id=call_id,
                            )
                        )
                        continue
                    tool_calls_used += 1
                    tool_responses.append(await _execute_editor_tool(fc, allowed_tool_names))
                current_message = tool_responses

            parsed = _extract_json(last_text)
            if parsed:
                return parsed
        except RateLimitExceeded as exc:
            log.warning("Edit planner quota exhausted; using fallback parser", sku=exc.sku)
            return None
        except Exception as exc:
            log.warning("Edit planner tool loop failed; retrying planner without tools", error=str(exc))

    try:
        await get_rate_limiter().consume(_edit_sku)
        resp = await runtime.model_client.aio.models.generate_content(
            model=_edit_model,
            contents=[json.dumps(prompt_body, default=str)],
            config=with_user_facing_output_policy(
                types.GenerateContentConfig(
                    system_instruction=EDIT_PLANNER_PROMPT,
                    temperature=0.1,
                    max_output_tokens=1400,
                    response_mime_type="application/json",
                )
            ),
        )
        return _extract_json(getattr(resp, "text", None))
    except RateLimitExceeded as exc:
        log.warning("Edit planner quota exhausted; using fallback parser", sku=exc.sku)
    except Exception as exc:
        log.warning("Edit planner failed; using fallback parser", error=str(exc))
    return None


def _message_has_structural_request(message: str) -> bool:
    return bool(
        re.search(
            r"\b(new trip|new itinerary|change (the )?(destination|origin|start date|end date)|extend trip|shorten trip|add a day|remove a day)\b",
            message,
            re.IGNORECASE,
        )
    )


def _extract_day_number(message: str) -> Optional[int]:
    m = re.search(r"\bday\s*#?\s*(\d+)\b", message, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_event_number(message: str) -> Optional[int]:
    patterns = (
        r"\bevent\s*#?\s*(\d+)\b",
        r"\b#\s*(\d+)\b",
    )
    for pattern in patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None


def _extract_duration_minutes(message: str) -> Optional[int]:
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(hours?|hrs?|h)\b", message, re.IGNORECASE)
    if m:
        return max(5, int(round(float(m.group(1)) * 60)))
    m = re.search(r"\b(\d+)\s*(minutes?|mins?|m)\b", message, re.IGNORECASE)
    if m:
        return max(5, int(m.group(1)))
    if re.search(r"\bshorten\b", message, re.IGNORECASE):
        return 45
    if re.search(r"\blengthen|extend\b", message, re.IGNORECASE):
        return 120
    return None


def _message_requests_duration(message: str) -> bool:
    if _extract_duration_minutes(message) is None:
        return False
    return bool(
        re.search(
            r"\b(shorten|lengthen|extend|duration|minutes?|mins?|hours?|hrs?|make\s+(?:it|this|that|this\s+event|that\s+event)\s+\d+)\b",
            message,
            re.IGNORECASE,
        )
    )


def _extract_time_text(message: str) -> str:
    m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", message, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        suffix = (m.group(3) or "").lower()
        if suffix == "pm" and hour < 12:
            hour += 12
        if suffix == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    m = re.search(r"\b(\d{1,2}:\d{2})\b", message)
    if m:
        return m.group(1)
    return ""


def _infer_event_type(message: str, name: str = "") -> str:
    text = f"{message} {name}".lower()
    if re.search(r"\b(dinner|lunch|breakfast|brunch|restaurant|cafe|coffee|bar|drinks|eat|food)\b", text):
        return "DINING"
    if re.search(r"\b(museum|tour|visit|park|show|hike|walk|attraction|gallery|activity|experience)\b", text):
        return "ACTIVITY"
    return "OTHER"


def _extract_requested_name(message: str, action: str) -> str:
    text = message.strip()
    patterns: list[str] = []
    if action == "add":
        patterns = [
            r"\badd\s+(?:a|an|the)?\s*(.+?)(?:\s+(?:on|to|at|before|after|between)\b|$)",
            r"\binclude\s+(?:a|an|the)?\s*(.+?)(?:\s+(?:on|to|at|before|after|between)\b|$)",
        ]
    elif action == "replace":
        patterns = [
            r"\b(?:replace|swap|change)\b.+?\b(?:with|to|for)\s+(.+?)(?:\s+(?:on|at|before|after)\b|$)",
        ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip(" .")
    return ""


_GENERIC_ADD_NAMES = {
    "event",
    "small event",
    "quick event",
    "short event",
    "activity",
    "small activity",
    "quick activity",
    "short activity",
    "stop",
    "quick stop",
    "small stop",
    "thing",
    "something",
    "anything",
    "break",
    "short break",
}


_CHAT_REFERENCE_RE = re.compile(
    r"\b(it|this|that|there|those|them|same|previous|above|option\s*\d+|one|second|third|first)\b",
    re.IGNORECASE,
)


def _is_generic_requested_event(name: str, message: str) -> bool:
    normalized = normalize_text(name)
    if normalized in _GENERIC_ADD_NAMES:
        return True
    if re.search(r"\b(small|quick|short)\s+(event|activity|stop|thing)\b", message, re.IGNORECASE):
        return True
    return False


def _clean_requested_event_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:minutes?|mins?|m|hours?|hrs?|h)\b",
        " ",
        raw,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-:")
    normalized = normalize_text(cleaned)
    if normalized in {"coffee", "coffee break", "cafe", "cafe break"}:
        return "Coffee Break"
    if normalized in {"breakfast", "lunch", "dinner", "brunch"}:
        return normalized.title()
    return cleaned or raw


def _extract_option_number(message: str) -> Optional[int]:
    text = message or ""
    m = re.search(r"\boption\s*(\d+)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(?:#|number)\s*(\d+)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    ordinals = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }
    for word, number in ordinals.items():
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            return number
    return None


def _clean_option_line(line: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line or "")
    bold = re.search(r"\*\*([^*]+)\*\*", text)
    if bold:
        return _clean_requested_event_name(bold.group(1))
    text = re.sub(r"^\s*(?:[-*]\s*)?(?:option\s*)?\d+\s*[\).\:-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[*_`]", "", text).strip()
    text = re.split(r"\s+[—–-]\s+|:", text, maxsplit=1)[0].strip()
    return _clean_requested_event_name(text)


def _option_name_from_chat_history(chat_history: list, option_number: Optional[int]) -> str:
    if not option_number or option_number <= 0:
        return ""
    for item in reversed(chat_history or []):
        if not isinstance(item, dict) or item.get("role") != "assistant":
            continue
        content = str(item.get("content") or "")
        option_lines: list[str] = []
        for line in content.splitlines():
            if re.match(r"^\s*(?:[-*]\s*)?(?:option\s*)?\d+\s*[\).\:-]", line, re.IGNORECASE):
                option_lines.append(line)
        if len(option_lines) >= option_number:
            name = _clean_option_line(option_lines[option_number - 1])
            if name:
                return name
        table_rows: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|") or "**" not in stripped:
                continue
            if re.search(r"\b(Restaurant|Hotel|Option|Rating|Price|Why)\b", stripped, re.IGNORECASE):
                continue
            table_rows.append(stripped)
        if len(table_rows) >= option_number:
            name = _clean_option_line(table_rows[option_number - 1])
            if name:
                return name
    return ""


def _fallback_plan(
    *,
    message: str,
    attached_events: list[dict[str, Any]],
) -> dict[str, Any]:
    lower = message.lower()
    if _message_has_structural_request(message):
        return {
            "action": "reject",
            "rejection_reason": "That is a trip-level structural change, not an event-level itinerary edit.",
        }

    action = "update_details"
    if re.search(r"\b(remove|delete|cancel|drop)\b", lower):
        action = "remove"
    elif re.search(r"\b(add|insert|include)\b", lower):
        action = "add"
    elif re.search(r"\b(replace|swap|change).+\b(with|to|for)\b", lower):
        action = "replace"
    elif re.search(r"\b(use|pick|select|choose|go with)\b.+\b(?:option\s*)?\d+\b", lower):
        action = "replace"
    elif re.search(r"\b(switch|change)\s+(?:it|this|that|the event|the place|the restaurant|the hotel)\s+(?:to|for)\b", lower):
        action = "replace"
    elif re.search(r"\b(move|shift|put)\b", lower):
        action = "move"
    elif re.search(r"\b(shorten|lengthen|extend|duration|make\s+(?:it|this|that|this\s+event|that\s+event)\s+\d+)\b", lower):
        action = "duration"
    elif re.search(r"\b(at|start|time|earlier|later|reschedule)\b", lower):
        action = "retime"

    day = _extract_day_number(message)
    event_number = _extract_event_number(message)
    target_refs: list[dict[str, Any]] = []
    if attached_events:
        first = attached_events[0]
        event = first.get("event_data") if isinstance(first, dict) else None
        target_refs.append({
            "event_id": (event or first).get("event_id"),
            "day_number": (event or first).get("day_number"),
            "event_number": (event or first).get("event_number"),
            "label": event_name(event) if isinstance(event, dict) else "",
        })
    elif day is not None and event_number is not None:
        target_refs.append({"day_number": day, "event_number": event_number, "event_id": "", "label": ""})

    name = _clean_requested_event_name(_extract_requested_name(message, action))
    return {
        "action": action,
        "confidence": 0.55,
        "target_refs": target_refs,
        "target_selector": message,
        "placement": {
            "day_number": day,
            "relation": "at_end",
            "reference_event_id": "",
            "reference_day_number": None,
            "reference_event_number": None,
        },
        "requested_event": {
            "event_type": _infer_event_type(message, name) if action in {"add", "replace"} else "",
            "name": name,
            "description": "",
            "location": name,
            "start_time": _extract_time_text(message),
            "end_time": "",
            "duration_minutes": _extract_duration_minutes(message),
            "cost": None,
            "notes": "",
        },
        "new_start_time": _extract_time_text(message),
        "duration_minutes": _extract_duration_minutes(message),
        "detail_updates": {},
        "destructive": action == "remove",
    }


def _fallback_is_actionable(plan: dict[str, Any], message: str, attached_events: list[dict[str, Any]]) -> bool:
    action = _plan_action(plan)
    if action in {"clarify", "reject"}:
        return False
    if action == "add":
        requested = plan.get("requested_event") if isinstance(plan.get("requested_event"), dict) else {}
        has_day_or_reference = _extract_day_number(message) is not None or _relation_from_message(message) in {"before", "after"}
        return bool(str(requested.get("name") or "").strip() or _extract_duration_minutes(message)) and has_day_or_reference
    if action in {"retime", "duration", "remove", "replace", "move", "update_details"}:
        if attached_events:
            return True
        if _extract_day_number(message) is not None and _extract_event_number(message) is not None:
            return True
        selector = normalize_text(str(plan.get("target_selector") or message))
        return len(selector.split()) >= 2
    return False


def _should_use_fallback_plan(
    *,
    llm_plan: dict[str, Any],
    fallback_plan: dict[str, Any],
    user_message: str,
    attached_events: list[dict[str, Any]],
) -> bool:
    fallback_action = _plan_action(fallback_plan)
    if not _fallback_is_actionable(fallback_plan, user_message, attached_events):
        return False

    llm_action = _plan_action(llm_plan)
    if llm_action in {"clarify", "reject"}:
        return True

    if fallback_action in {"remove", "add", "replace", "move", "retime", "duration"} and llm_action == "update_details":
        return True

    if fallback_action == "duration" and _message_requests_duration(user_message):
        return True

    return False


def _plan_action(plan: dict[str, Any]) -> str:
    action = str(plan.get("action") or "").lower().strip()
    if action in {"clarify", "reject", "add", "remove", "replace", "move", "retime", "duration", "update_details"}:
        return action
    return "clarify"


def _resolve_ref(ref: dict[str, Any], events: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    event_id = ref.get("event_id")
    if isinstance(event_id, str) and event_id:
        event = event_by_id(events, event_id)
        if event is not None:
            return event
    day = ref.get("day_number")
    num = ref.get("event_number")
    if isinstance(day, int) and isinstance(num, int):
        return event_by_legacy_ref(events, day, num)
    return None


def _resolve_targets(
    *,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
    attached_events: list[dict[str, Any]],
    user_message: str,
    chat_history: list,
    required: bool = True,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    targets: list[dict[str, Any]] = []
    for ref in plan.get("target_refs") or []:
        if isinstance(ref, dict):
            event = _resolve_ref(ref, events)
            if event is not None:
                targets.append(event)

    if not targets and attached_events:
        for item in attached_events:
            event = item.get("event_data") if isinstance(item, dict) else None
            if isinstance(event, dict):
                resolved = event_by_id(events, event.get("event_id")) if event.get("event_id") else None
                if resolved is None:
                    resolved = event_by_legacy_ref(events, event.get("day_number"), event.get("event_number"))
                if resolved is not None:
                    targets.append(resolved)

    if not targets:
        day = _extract_day_number(user_message)
        num = _extract_event_number(user_message)
        if day is not None and num is not None:
            event = event_by_legacy_ref(events, day, num)
            if event is not None:
                targets.append(event)

    if not targets:
        selector = normalize_text(_target_selector_text(plan, user_message))
        if selector:
            scored: list[tuple[int, dict[str, Any]]] = []
            selector_tokens = {
                tok for tok in selector.split()
                if len(tok) > 2 and tok not in _TARGET_SELECTOR_STOP_WORDS
            }
            for event in regular_events(events):
                haystack = normalize_text(f"{event_name(event)} {event_description(event)} {event.get('event_type')}")
                score = sum(1 for tok in selector_tokens if tok in haystack)
                if event.get("event_type") == "DINING" and selector_tokens & {"restaurant", "dinner", "lunch", "breakfast", "brunch", "cafe", "coffee"}:
                    score += 2
                if event.get("event_type") != "DINING" and selector_tokens <= {"restaurant", "dinner", "lunch", "breakfast", "brunch", "cafe", "coffee"}:
                    score = 0
                if score > 0:
                    scored.append((score, event))
            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                best_score = scored[0][0]
                best = [event for score, event in scored if score == best_score]
                if len(best) == 1:
                    targets.append(best[0])
                elif required:
                    labels = ", ".join(
                        f"Day {e.get('day_number')} event {e.get('event_number')} ({event_name(e)})"
                        for e in best[:5]
                    )
                    return [], f"I found multiple possible events: {labels}. Which one should I edit?"

    if not targets:
        target = _event_from_chat_history_context(
            events=events,
            chat_history=chat_history,
            user_message=user_message,
        )
        if target is not None:
            targets.append(target)

    if not targets and required:
        return [], "Which event should I edit? You can attach the event or say the day and event number."

    dedup: dict[str, dict[str, Any]] = {}
    for event in targets:
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            dedup[event_id] = event
    return list(dedup.values()), None


def _expand_booking_groups(events: list[dict[str, Any]], targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: dict[str, dict[str, Any]] = {}
    for target in targets:
        members = group_members(events, target) if target.get("event_type") in BOOKING_PAIR_TYPES else [target]
        for member in members:
            event_id = member.get("event_id")
            if isinstance(event_id, str):
                expanded[event_id] = member
    return sorted(expanded.values(), key=day_sort_key)


def _locked_target_reason(targets: list[dict[str, Any]]) -> Optional[str]:
    locked = [target for target in targets if is_locked(target)]
    if not locked:
        return None
    labels = ", ".join(
        f"Day {event.get('day_number')} event {event.get('event_number')} ({event_name(event)})"
        for event in locked
    )
    return f"I cannot edit locked itinerary events. Locked target: {labels}."


def _trip_destination_label(trip_input: dict[str, Any], day_number: int) -> str:
    destinations = trip_input.get("destinations") or []
    if isinstance(destinations, list) and destinations:
        idx = min(max(day_number - 1, 0), len(destinations) - 1)
        dest = destinations[idx]
        if isinstance(dest, dict):
            return dest.get("city") or dest.get("name") or dest.get("label") or ""
        if isinstance(dest, str):
            return dest
    origin = trip_input.get("origin")
    if isinstance(origin, dict):
        return origin.get("city") or origin.get("name") or ""
    return ""


def _find_first_lat_lng(value: Any) -> Optional[tuple[float, float]]:
    if isinstance(value, dict):
        lat = value.get("lat", value.get("latitude"))
        lng = value.get("lng", value.get("longitude"))
        if lat is not None and lng is not None:
            try:
                return float(lat), float(lng)
            except (TypeError, ValueError):
                pass
        for child in value.values():
            found = _find_first_lat_lng(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_first_lat_lng(child)
            if found:
                return found
    return None


def _fallback_coordinates(
    *,
    events: list[dict[str, Any]],
    trip_input: dict[str, Any],
    day_number: int,
) -> tuple[float, float]:
    day_events = day_boundaries(events, day_number)
    for event in reversed(day_events):
        _, dest = event_origin_dest(event)
        if dest:
            return dest
    found = _find_first_lat_lng(trip_input.get("destinations")) or _find_first_lat_lng(trip_input.get("origin"))
    if found:
        return found
    return 0.0, 0.0


def _event_anchor_coords(event: Optional[dict[str, Any]]) -> Optional[tuple[float, float]]:
    if not isinstance(event, dict):
        return None
    origin, destination = event_origin_dest(event)
    return destination or origin


def _search_query_for_event(
    *,
    requested_name: str,
    requested_location: str,
    event_type: str,
    nearby_event: Optional[dict[str, Any]],
    destination_label: str,
) -> str:
    name = requested_location or requested_name
    normalized = normalize_text(name)
    if "coffee" in normalized and "shop" not in normalized and "cafe" not in normalized:
        name = "coffee shop"
    elif event_type == "DINING" and normalized in {"breakfast", "lunch", "dinner", "brunch"}:
        name = f"{normalized} restaurant"

    nearby_label = event_location_name(nearby_event) if nearby_event else ""
    context = nearby_label or destination_label
    return " ".join(part for part in (name, context) if part)


async def _search_place(query: str) -> Optional[dict[str, Any]]:
    if runtime.mcp_session is None or not query.strip():
        return None
    args = {
        "query": query,
        "include_dining_options": False,
        "include_amenities": False,
        "max_results": 5,
        "place_index": 0,
    }
    call_id = str(uuid.uuid4())
    emit({"type": "tool_call", "tool_name": "search_places", "args": args, "call_id": call_id})
    try:
        result = await asyncio.wait_for(
            runtime.mcp_session.call_tool("search_places", args),
            timeout=20,
        )
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        data = json.loads(text) if text else {}
        place = data.get("place")
        return place if isinstance(place, dict) else None
    except Exception as exc:
        log.info("Place enrichment failed; using fallback event details", error=str(exc))
        return None


def _nearby_place_types(event_type: str, requested_name: str, message: str) -> list[str]:
    text = normalize_text(f"{requested_name} {message}")
    if re.search(r"\b(coffee|cafe|espresso|latte)\b", text):
        return ["coffee_shop", "cafe", "coffee_stand"]
    if re.search(r"\b(breakfast|brunch)\b", text):
        return ["breakfast_restaurant", "brunch_restaurant", "cafe", "restaurant"]
    if re.search(r"\b(lunch|dinner|restaurant|meal|food|eat|snack)\b", text):
        return ["restaurant", "cafe"]
    if "bakery" in text:
        return ["bakery", "cafe"]
    if re.search(r"\b(bar|drinks|cocktail)\b", text):
        return ["bar", "cocktail_bar"]
    if "museum" in text:
        return ["museum"]
    if "gallery" in text:
        return ["art_gallery"]
    if "park" in text:
        return ["park"]
    if re.search(r"\b(attraction|tour|visit|walk|activity|experience)\b", text):
        return ["tourist_attraction", "museum", "park"]
    if event_type == "DINING":
        return ["restaurant", "cafe"]
    if event_type == "ACTIVITY":
        return ["tourist_attraction", "museum", "park"]
    return []


def _prefer_nearby_place_search(event_type: str, requested_name: str, message: str) -> bool:
    text = normalize_text(f"{requested_name} {message}")
    return bool(
        re.search(
            r"\b(coffee|cafe|breakfast|brunch|lunch|dinner|restaurant|meal|food|snack|bakery|bar|drinks|museum|gallery|park|attraction|tour|walk|activity|experience)\b",
            text,
        )
    )


def _looks_like_specific_place_name(name: str, requested_location: str) -> bool:
    text = normalize_text(requested_location or name)
    if not text:
        return False
    generic = {
        "activity",
        "bar",
        "break",
        "breakfast",
        "breakfast restaurant",
        "brunch",
        "brunch restaurant",
        "cafe",
        "coffee",
        "coffee break",
        "coffee shop",
        "dinner",
        "dinner restaurant",
        "food",
        "lunch",
        "lunch restaurant",
        "museum",
        "park",
        "restaurant",
        "snack",
        "tour",
        "tourist attraction",
        "vegetarian restaurant",
        "vegan restaurant",
    }
    if text in generic:
        return False
    tokens = [token for token in text.split() if token not in {"a", "an", "the"}]
    return len(tokens) >= 2


async def _search_place_nearby(
    *,
    anchor_coords: tuple[float, float],
    included_types: list[str],
    event_type: str,
) -> Optional[dict[str, Any]]:
    if runtime.mcp_session is None or not included_types:
        return None
    if anchor_coords == (0.0, 0.0):
        return None
    args = {
        "lat": float(anchor_coords[0]),
        "lng": float(anchor_coords[1]),
        "included_types": included_types,
        "radius": _NEARBY_SEARCH_RADIUS_M,
        "include_dining_options": event_type == "DINING",
        "include_amenities": False,
        "max_results": 10,
        "rank_preference": "DISTANCE",
        "excluded_types": [],
        "place_index": 0,
    }
    call_id = str(uuid.uuid4())
    emit({"type": "tool_call", "tool_name": "search_places_nearby", "args": args, "call_id": call_id})
    try:
        result = await asyncio.wait_for(
            runtime.mcp_session.call_tool("search_places_nearby", args),
            timeout=TIMEOUTS.get("search_places_nearby", 60),
        )
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        data = json.loads(text) if text else {}
        place = data.get("place")
        return place if isinstance(place, dict) else None
    except Exception as exc:
        log.info("Nearby place enrichment failed; trying text search fallback", error=str(exc))
        return None


def _place_coords_tuple(place: Optional[dict[str, Any]]) -> Optional[tuple[float, float]]:
    location = (place or {}).get("location") if isinstance(place, dict) else None
    if not isinstance(location, dict):
        return None
    lat = location.get("latitude")
    lng = location.get("longitude")
    try:
        if lat is not None and lng is not None:
            return float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    return None


def _place_distance_m(place: Optional[dict[str, Any]], anchor_coords: tuple[float, float]) -> Optional[float]:
    coords = _place_coords_tuple(place)
    if coords is None:
        return None
    return _estimate_distance_m(anchor_coords, coords)


def _coords_from_place(place: Optional[dict[str, Any]], fallback: tuple[float, float]) -> dict[str, float]:
    location = (place or {}).get("location") if isinstance(place, dict) else None
    if isinstance(location, dict):
        lat = location.get("latitude")
        lng = location.get("longitude")
        try:
            if lat is not None and lng is not None:
                return {"latitude": float(lat), "longitude": float(lng)}
        except (TypeError, ValueError):
            pass
    return {"latitude": fallback[0], "longitude": fallback[1]}


def _parse_requested_datetime(value: Any, day_date: str) -> Optional[datetime]:
    parsed = parse_dt(value)
    if parsed:
        if len(str(value)) <= 5 and day_date:
            return datetime.combine(datetime.fromisoformat(day_date).date(), parsed.time())
        return parsed
    if not isinstance(value, str) or not value.strip() or not day_date:
        return None
    raw = value.strip()
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", raw, re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    suffix = (m.group(3) or "").lower()
    if suffix == "pm" and hour < 12:
        hour += 12
    if suffix == "am" and hour == 12:
        hour = 0
    try:
        return datetime.combine(datetime.fromisoformat(day_date).date(), time(hour, minute))
    except Exception:
        return None


def _estimate_distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1 = a
    lat2, lng2 = b
    radius = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _waypoint_from_coords(coords: tuple[float, float]) -> dict[str, float]:
    return {"lat": float(coords[0]), "lng": float(coords[1])}


async def _route_between(
    *,
    origin_coords: tuple[float, float],
    dest_coords: tuple[float, float],
) -> Optional[dict[str, Any]]:
    if runtime.mcp_session is None:
        return None
    if origin_coords == (0.0, 0.0) or dest_coords == (0.0, 0.0):
        return None
    args = {
        "origin": _waypoint_from_coords(origin_coords),
        "destination": _waypoint_from_coords(dest_coords),
        "intermediate_waypoints": [],
        "travel_mode": "DRIVE",
        "routing_preference": "TRAFFIC_AWARE",
        "units_system": "IMPERIAL",
        "compute_alternative_routes": False,
        "optimize_waypoint_order": False,
    }
    call_id = str(uuid.uuid4())
    emit({"type": "tool_call", "tool_name": "get_route", "args": args, "call_id": call_id})
    try:
        result = await asyncio.wait_for(
            runtime.mcp_session.call_tool("get_route", args),
            timeout=TIMEOUTS.get("get_route", 60),
        )
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        payload = json.loads(text) if text else {}
        route = (payload.get("routes") or [None])[0]
        return route if isinstance(route, dict) else None
    except Exception as exc:
        log.info("Route enrichment failed for edit commute; using coordinate fallback", error=str(exc))
        return None


def _maps_url_from_coords(origin_coords: tuple[float, float], dest_coords: tuple[float, float]) -> str:
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin_coords[0]},{origin_coords[1]}"
        f"&destination={dest_coords[0]},{dest_coords[1]}"
        "&travelmode=driving"
    )


async def _make_commute_event(
    *,
    events: list[dict[str, Any]],
    day_number: int,
    sort_key: float,
    origin_event: dict[str, Any],
    destination_event: dict[str, Any],
) -> dict[str, Any]:
    _, origin_dest = event_origin_dest(origin_event)
    dest_origin, _ = event_origin_dest(destination_event)
    origin_coords = origin_dest or (0.0, 0.0)
    dest_coords = dest_origin or origin_coords
    route = await _route_between(origin_coords=origin_coords, dest_coords=dest_coords)
    distance = finite_float((route or {}).get("distanceMeters"), _estimate_distance_m(origin_coords, dest_coords))
    duration = int(
        finite_float(
            (route or {}).get("durationWithTrafficSeconds"),
            finite_float((route or {}).get("durationWithoutTrafficSeconds"), max(600, min(7200, int(distance / 10.0) + 600))),
        )
    )
    duration = max(300, duration)
    warnings = (route or {}).get("warnings") or []
    maps_url = str((route or {}).get("mapsUrl") or _maps_url_from_coords(origin_coords, dest_coords))
    commute_tips = "; ".join(str(item) for item in warnings if str(item).strip())
    if not commute_tips:
        commute_tips = "Check live traffic and route conditions before leaving."
    origin_name = event_location_name(origin_event)
    dest_name = event_location_name(destination_event)
    event_number = next_legacy_event_number(events, day_number)
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "event_sort_key": sort_key,
        "day_number": day_number,
        "event_number": event_number,
        "day_title": day_title(day_number, events),
        "date": destination_event.get("date") or origin_event.get("date"),
        "event_type": "COMMUTE",
        "is_locked": False,
        "commute_details": {
            "originName": origin_name,
            "destinationName": dest_name,
            "origin_coordinates": {"latitude": origin_coords[0], "longitude": origin_coords[1]},
            "destination_coordinates": {"latitude": dest_coords[0], "longitude": dest_coords[1]},
            "travel_mode": "DRIVE",
            "distanceMeters": round(distance, 1),
            "durationSeconds": duration,
            "commute_tips": commute_tips,
            "transit_fare": 0.0,
            "maps_url": maps_url,
        },
    }


def _insert_event(events: list[dict[str, Any]], event: dict[str, Any]) -> list[dict[str, Any]]:
    return canonicalize_events([*copy.deepcopy(events), copy.deepcopy(event)])


def _adjacent_regular_events(
    events: list[dict[str, Any]],
    event: dict[str, Any],
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    day_events = day_boundaries(events, int(event.get("day_number") or 0))
    event_id = event.get("event_id")
    for idx, candidate in enumerate(day_events):
        if candidate.get("event_id") == event_id:
            before = day_events[idx - 1] if idx > 0 else None
            after = day_events[idx + 1] if idx + 1 < len(day_events) else None
            return before, after
    return None, None


def _collect_adjacent_unlocked_commutes(events: list[dict[str, Any]], targets: list[dict[str, Any]]) -> set[str]:
    removable: set[str] = set()
    target_ids = {target.get("event_id") for target in targets}
    for target in targets:
        before, after = _adjacent_regular_events(events, target)
        for candidate in (before, after):
            event_id = candidate.get("event_id") if isinstance(candidate, dict) else None
            if (
                isinstance(candidate, dict)
                and candidate.get("event_type") == "COMMUTE"
                and event_id not in target_ids
                and not is_locked(candidate)
            ):
                removable.add(str(event_id))
    return removable


def _remove_with_commutes(events: list[dict[str, Any]], targets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[str]]:
    event_ids = {str(target.get("event_id")) for target in targets if target.get("event_id")}
    event_ids.update(_collect_adjacent_unlocked_commutes(events, targets))
    return remove_event_ids(events, event_ids), event_ids


def _relation_from_message(message: str, default: str = "at_end") -> str:
    lower = message.lower()
    if " before " in f" {lower} ":
        return "before"
    if " after " in f" {lower} ":
        return "after"
    if re.search(r"\b(start|beginning)\b", lower):
        return "at_start"
    if re.search(r"\b(end|last)\b", lower):
        return "at_end"
    return default


_PLACEMENT_REFERENCE_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "event",
    "it",
    "place",
    "stop",
    "the",
    "this",
    "that",
    "to",
}

_TARGET_SELECTOR_STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "change",
    "delete",
    "drop",
    "edit",
    "event",
    "for",
    "from",
    "it",
    "make",
    "move",
    "put",
    "remove",
    "replace",
    "swap",
    "that",
    "the",
    "this",
    "to",
    "update",
    "with",
}


def _relation_reference_phrase(message: str, relation: str) -> str:
    if relation not in {"before", "after"}:
        return ""
    match = re.search(rf"\b{relation}\b\s+(.+)", message, re.IGNORECASE)
    if not match:
        return ""
    fragment = match.group(1)
    fragment = re.split(r"\b(?:on|in)\s+day\s*#?\s*\d+\b|[,.!?;]", fragment, maxsplit=1)[0]
    fragment = re.sub(r"\b(?:at|around)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b.*$", "", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"\bfor\s+\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b.*$", "", fragment, flags=re.IGNORECASE)
    return normalize_text(fragment)


def _score_reference_match(event: dict[str, Any], phrase: str) -> int:
    tokens = {
        token for token in normalize_text(phrase).split()
        if len(token) > 1 and token not in _PLACEMENT_REFERENCE_STOP_WORDS
    }
    if not tokens:
        return 0
    event_type = str(event.get("event_type") or "")
    include_commutes = bool(tokens & {"commute", "drive", "transfer", "ride"})
    if event_type == "COMMUTE" and not include_commutes:
        return 0

    haystack = normalize_text(
        f"{event_name(event)} {event_description(event)} {event_location_name(event)} {event_type}"
    )
    if not haystack:
        return 0

    score = 0
    phrase_norm = normalize_text(phrase)
    if phrase_norm and phrase_norm in haystack:
        score += 10
    haystack_tokens = set(haystack.split())
    for token in tokens:
        if token in haystack_tokens:
            score += 4
        elif token in haystack:
            score += 2

    meal_terms = {"breakfast", "brunch", "lunch", "dinner", "restaurant", "coffee", "cafe", "bar"}
    if event_type == "DINING" and tokens & meal_terms:
        score += 4
    if event_type in {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"} and tokens & {"hotel", "checkin", "checkout", "lodging"}:
        score += 4
    if event_type in {"ACTIVITY", "OTHER"} and tokens & {"activity", "visit", "tour", "museum", "show", "walk"}:
        score += 3
    return score


def _target_selector_text(plan: dict[str, Any], user_message: str) -> str:
    action = _plan_action(plan)
    if action == "replace":
        m = re.search(
            r"\b(?:replace|swap|change)\s+(.+?)\s+(?:with|to|for)\b",
            user_message,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
    if action == "remove":
        m = re.search(r"\b(?:remove|delete|cancel|drop)\s+(.+)", user_message, re.IGNORECASE)
        if m:
            return m.group(1)
    return str(plan.get("target_selector") or user_message)


def _event_matches_meal_reference(event: dict[str, Any], content: str, day: Optional[int]) -> bool:
    if day is not None and event.get("day_number") != day:
        return False
    if event.get("event_type") != "DINING":
        return False
    text = normalize_text(content)
    meal_terms = {"breakfast", "brunch", "lunch", "dinner", "restaurant", "cafe", "coffee"}
    terms = {term for term in meal_terms if re.search(rf"\b{term}\b", text)}
    if not terms:
        return False
    haystack = normalize_text(f"{event_name(event)} {event_description(event)}")
    return bool(terms & set(haystack.split()) or terms & {"restaurant"})


def _event_matches_lodging_reference(event: dict[str, Any], content: str, day: Optional[int]) -> bool:
    if day is not None and event.get("day_number") != day:
        return False
    if event.get("event_type") not in {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"}:
        return False
    return bool(re.search(r"\b(hotel|lodging|stay|check-?in|check-?out)\b", content, re.IGNORECASE))


def _event_from_chat_history_context(
    *,
    events: list[dict[str, Any]],
    chat_history: list,
    user_message: str,
) -> Optional[dict[str, Any]]:
    if not _CHAT_REFERENCE_RE.search(user_message or ""):
        return None

    history_items = [
        str(item.get("content") or "")
        for item in (chat_history or [])[-8:]
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
    for content in reversed(history_items):
        normalized_content = normalize_text(content)
        direct_matches: list[dict[str, Any]] = []
        for event in regular_events(events):
            name = normalize_text(event_name(event))
            location = normalize_text(event_location_name(event))
            if (
                (len(name) >= 5 and name in normalized_content)
                or (len(location) >= 5 and location in normalized_content)
            ):
                direct_matches.append(event)
        if len(direct_matches) == 1:
            return direct_matches[0]

        day = _extract_day_number(content)
        meal_matches = [event for event in regular_events(events, day) if _event_matches_meal_reference(event, content, day)]
        if len(meal_matches) == 1:
            return meal_matches[0]

        hotel_matches = [event for event in regular_events(events, day) if _event_matches_lodging_reference(event, content, day)]
        if len(hotel_matches) == 1:
            return hotel_matches[0]
        if len(hotel_matches) > 1:
            checkin = next((event for event in hotel_matches if event.get("event_type") == "HOTEL_CHECKIN"), None)
            if checkin is not None:
                return checkin
    return None


def _augment_plan_from_chat_history(
    *,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
    chat_history: list,
    user_message: str,
) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    action = _plan_action(result)

    option_number = _extract_option_number(user_message)
    option_name = _option_name_from_chat_history(chat_history, option_number)
    if option_name:
        requested = result.get("requested_event") if isinstance(result.get("requested_event"), dict) else {}
        requested = dict(requested)
        current_name = normalize_text(str(requested.get("name") or ""))
        if not current_name or current_name.startswith("option") or current_name in {"first", "second", "third"}:
            requested["name"] = option_name
            requested["location"] = option_name
        result["requested_event"] = requested

    if action not in {"add", "clarify", "reject"}:
        target = _event_from_chat_history_context(
            events=events,
            chat_history=chat_history,
            user_message=user_message,
        )
        should_prefer_chat_target = (
            target is not None
            and (
                option_number is not None
                or not result.get("target_refs")
                or normalize_text(str(result.get("target_selector") or "")) in {"it", "this", "that", "there"}
            )
        )
        if should_prefer_chat_target and target is not None:
            result["target_refs"] = [{
                "event_id": target.get("event_id"),
                "day_number": target.get("day_number"),
                "event_number": target.get("event_number"),
                "label": event_name(target),
            }]
            selector = normalize_text(str(result.get("target_selector") or ""))
            if not selector or selector in {"it", "this", "that", "there", "option", "option 1", "option 2", "option 3"}:
                result["target_selector"] = event_name(target)

    return result


def _message_requests_venue_replacement(user_message: str, plan: dict[str, Any]) -> bool:
    text = normalize_text(user_message)
    if re.search(r"\b(use|pick|select|choose|go with)\b.+\b(?:option\s*)?\d+\b", user_message, re.IGNORECASE):
        return True
    if re.search(r"\b(replace|swap|switch)\b", user_message, re.IGNORECASE):
        return True
    if re.search(r"\bchange\b.+\b(to|for|with)\b", user_message, re.IGNORECASE) and re.search(
        r"\b(place|restaurant|hotel|activity|venue|cafe|coffee|dinner|lunch|breakfast|option)\b",
        user_message,
        re.IGNORECASE,
    ):
        return True
    requested = plan.get("requested_event") if isinstance(plan.get("requested_event"), dict) else {}
    name = normalize_text(str(requested.get("name") or requested.get("location") or ""))
    return bool(name and name.startswith("option"))


def _message_reference_event(
    *,
    events: list[dict[str, Any]],
    user_message: str,
    day_number: Optional[int],
    relation: str,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    if relation not in {"before", "after", "same_slot"}:
        return None, None

    explicit = re.search(
        rf"\b{relation}\b\s+(?:(?:day\s*#?\s*(\d+))\s*)?(?:event\s*#?\s*(\d+)|#\s*(\d+))\b",
        user_message,
        re.IGNORECASE,
    )
    if explicit:
        ref_day = int(explicit.group(1)) if explicit.group(1) else day_number
        ref_num = int(explicit.group(2) or explicit.group(3))
        if isinstance(ref_day, int):
            event = event_by_legacy_ref(events, ref_day, ref_num)
            if event is not None:
                return event, None

    phrase = _relation_reference_phrase(user_message, relation)
    if not phrase:
        return None, None

    candidates = regular_events(events, day_number if isinstance(day_number, int) else None)
    scored = [
        (_score_reference_match(event, phrase), event)
        for event in candidates
    ]
    scored = [(score, event) for score, event in scored if score > 0]
    if not scored:
        return None, f"Which event should I place this {relation}? I could not find an event matching '{phrase}'."

    scored.sort(key=lambda item: (item[0], -float(item[1].get("event_sort_key") or 0)), reverse=True)
    best_score = scored[0][0]
    best = [event for score, event in scored if score == best_score]
    if len(best) == 1:
        return best[0], None

    labels = ", ".join(
        f"Day {event.get('day_number')} event {event.get('event_number')} ({event_name(event)})"
        for event in best[:5]
    )
    return None, f"I found multiple possible reference events for '{phrase}': {labels}. Which one should I use?"


def _resolve_placement(
    *,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    user_message: str,
) -> tuple[int, str, Optional[dict[str, Any]], Optional[str]]:
    placement = plan.get("placement") if isinstance(plan.get("placement"), dict) else {}
    # User text is the highest-trust source for explicit day/relation. Some
    # cheap planner models drift on numeric references even with strict JSON.
    day = _extract_day_number(user_message) or placement.get("day_number")
    relation = _relation_from_message(user_message, str(placement.get("relation") or "at_end"))
    if relation not in {"before", "after", "at_start", "at_end", "same_slot"}:
        relation = _relation_from_message(user_message)

    ref: Optional[dict[str, Any]] = None
    message_ref, message_question = _message_reference_event(
        events=events,
        user_message=user_message,
        day_number=day if isinstance(day, int) else None,
        relation=relation,
    )
    if message_ref is not None:
        ref = message_ref
    ref_id = placement.get("reference_event_id")
    if ref is None and isinstance(ref_id, str) and ref_id:
        ref = event_by_id(events, ref_id)
    if ref is None:
        ref_day = placement.get("reference_day_number")
        ref_num = placement.get("reference_event_number")
        if isinstance(ref_day, int) and isinstance(ref_num, int):
            ref = event_by_legacy_ref(events, ref_day, ref_num)
    if ref is None and targets and relation in {"before", "after", "same_slot"}:
        ref = targets[0]
    if ref is None and message_question:
        return 0, relation, ref, message_question

    if day is None and ref is not None:
        day = ref.get("day_number")
    if day is None and targets:
        day = targets[0].get("day_number")
    if day is None:
        day = 1
    if not isinstance(day, int) or day <= 0:
        return 0, relation, ref, "Which trip day should this edit use?"

    return day, relation, ref, None


def _commutes_displaced_by_insertion(
    events: list[dict[str, Any]],
    reference: Optional[dict[str, Any]],
    relation: str,
) -> set[str]:
    if reference is None or relation not in {"before", "after"}:
        return set()
    before, after = _adjacent_regular_events(events, reference)
    candidate = after if relation == "after" else before
    if (
        isinstance(candidate, dict)
        and candidate.get("event_type") == "COMMUTE"
        and not is_locked(candidate)
        and candidate.get("event_id")
    ):
        return {str(candidate["event_id"])}
    return set()


def _sort_key_for_placement(
    *,
    events: list[dict[str, Any]],
    day_number: int,
    relation: str,
    reference: Optional[dict[str, Any]],
) -> float:
    day_events = day_boundaries(events, day_number)
    if not day_events:
        return SORT_STEP
    if relation == "at_start":
        return sort_key_between(None, day_events[0], SORT_STEP / 2)
    if relation == "at_end":
        return sort_key_between(day_events[-1], None, (len(day_events) + 1) * SORT_STEP)
    if reference is None:
        return sort_key_between(day_events[-1], None, (len(day_events) + 1) * SORT_STEP)
    for idx, event in enumerate(day_events):
        if event.get("event_id") != reference.get("event_id"):
            continue
        if relation == "before":
            before = day_events[idx - 1] if idx > 0 else None
            return sort_key_between(before, event, float(event.get("event_sort_key") or SORT_STEP) - 1)
        if relation == "after":
            after = day_events[idx + 1] if idx + 1 < len(day_events) else None
            return sort_key_between(event, after, float(event.get("event_sort_key") or SORT_STEP) + 1)
        return float(event.get("event_sort_key") or SORT_STEP)
    return sort_key_between(day_events[-1], None, (len(day_events) + 1) * SORT_STEP)


def _default_start_for_placement(
    *,
    events: list[dict[str, Any]],
    trip_input: dict[str, Any],
    day_number: int,
    sort_key: float,
    duration_minutes: int,
    explicit_start: Optional[datetime],
) -> datetime:
    day_date = date_for_day(trip_input, day_number)
    candidate_day = ""
    for event in events:
        if event.get("day_number") == day_number and isinstance(event.get("date"), str):
            candidate_day = event["date"]
            break
    if not candidate_day:
        candidate_day = day_date
    if explicit_start is not None:
        return explicit_start
    try:
        base_date = datetime.fromisoformat(candidate_day).date()
    except Exception:
        base_date = datetime.utcnow().date()

    before = None
    after = None
    for event in day_boundaries(events, day_number):
        key = float(event.get("event_sort_key") or 0)
        if key < sort_key:
            before = event
        elif key > sort_key and after is None:
            after = event
            break

    start = datetime.combine(base_date, time(9, 0))
    before_end = event_end(before) if before else None
    if before_end:
        start = max(start, before_end + timedelta(minutes=20))
    after_start = event_start(after) if after else None
    if after_start and start + timedelta(minutes=duration_minutes) > after_start:
        start = after_start - timedelta(minutes=duration_minutes + 20)
    return start


def _default_event_description(event_type: str, place_name: str, requested_name: str) -> str:
    label = place_name or requested_name or "this stop"
    text = normalize_text(requested_name)
    if event_type == "DINING":
        if "coffee" in text:
            return f"A short coffee stop at {label} to recharge before continuing the day."
        if "breakfast" in text or "lunch" in text or "dinner" in text or "brunch" in text:
            return f"A planned meal at {label}, timed to fit the surrounding itinerary."
        return f"A dining stop at {label}, selected to fit the day route and timing."
    if event_type == "ACTIVITY":
        return f"Time set aside for {label}, with enough room to arrive, explore, and continue comfortably."
    return f"A flexible stop at {label}, placed around the surrounding itinerary timing."


def _default_event_tips(event_type: str) -> str:
    if event_type == "DINING":
        return "Check current hours and consider a reservation if the timing is tight."
    if event_type == "ACTIVITY":
        return "Confirm current hours, tickets, and any entry requirements before heading out."
    return "Confirm details before you go and leave a little buffer around this stop."


async def _build_place_like_event(
    *,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
    trip_input: dict[str, Any],
    day_number: int,
    sort_key: float,
    user_message: str,
    existing_event: Optional[dict[str, Any]] = None,
    nearby_event: Optional[dict[str, Any]] = None,
    require_real_place: bool = False,
) -> dict[str, Any]:
    requested = plan.get("requested_event") if isinstance(plan.get("requested_event"), dict) else {}
    name = _clean_requested_event_name(
        str(requested.get("name") or "").strip()
        or _extract_requested_name(user_message, "add")
        or (f"Updated {event_name(existing_event)}" if existing_event else "New itinerary event")
    )
    event_type = str(requested.get("event_type") or "").strip().upper()
    if event_type not in {"DINING", "ACTIVITY", "OTHER"}:
        event_type = _infer_event_type(user_message, name)

    day_date = date_for_day(trip_input, day_number)
    duration = requested.get("duration_minutes") or plan.get("duration_minutes") or _extract_duration_minutes(user_message) or event_duration_minutes(existing_event or {}, 60)
    duration = max(5, int(duration))
    explicit_start = _parse_requested_datetime(
        requested.get("start_time") or plan.get("new_start_time") or _extract_time_text(user_message),
        day_date,
    )
    start = _default_start_for_placement(
        events=events,
        trip_input=trip_input,
        day_number=day_number,
        sort_key=sort_key,
        duration_minutes=duration,
        explicit_start=explicit_start,
    )
    end = start + timedelta(minutes=duration)

    location = str(requested.get("location") or name).strip()
    destination_label = _trip_destination_label(trip_input, day_number)
    specific_place_name = _looks_like_specific_place_name(name, location)
    if specific_place_name:
        query = " ".join(part for part in (location or name, destination_label) if part)
    else:
        query = _search_query_for_event(
            requested_name=name,
            requested_location=location,
            event_type=event_type,
            nearby_event=nearby_event or existing_event,
            destination_label=destination_label,
        )
    fallback = (
        _event_anchor_coords(nearby_event)
        or _event_anchor_coords(existing_event)
        or _fallback_coordinates(events=events, trip_input=trip_input, day_number=day_number)
    )
    anchor_coords = _event_anchor_coords(nearby_event or existing_event)
    nearby_types = _nearby_place_types(event_type, name, user_message)
    prefer_nearby = _prefer_nearby_place_search(event_type, name, user_message)
    use_nearby_first = bool(
        anchor_coords
        and nearby_types
        and prefer_nearby
        and not specific_place_name
    )

    place: Optional[dict[str, Any]] = None
    if use_nearby_first and anchor_coords:
        place = await _search_place_nearby(
            anchor_coords=anchor_coords,
            included_types=nearby_types,
            event_type=event_type,
        )
    if place is None:
        place = await _search_place(query)
    if anchor_coords and place is not None and nearby_types and prefer_nearby and not specific_place_name:
        distance = _place_distance_m(place, anchor_coords)
        if distance is not None and distance > _RELATIVE_PLACE_MAX_DISTANCE_M:
            nearby_place = await _search_place_nearby(
                anchor_coords=anchor_coords,
                included_types=nearby_types,
                event_type=event_type,
            )
            if nearby_place is not None:
                place = nearby_place
            elif use_nearby_first:
                raise EditClarification(f"I could not find a nearby real place for {name}. Which exact place should I add?")
    if require_real_place and event_type in {"DINING", "ACTIVITY", "OTHER"} and place is None:
        raise EditClarification(f"I could not find a real place match for {name}. Which exact place should I use?")
    coords = _coords_from_place(place, fallback)

    place_name = (place or {}).get("name") or name
    address = ((place or {}).get("location") or {}).get("address") or location or destination_label or place_name
    place_id = (place or {}).get("id") or ""
    urls = (place or {}).get("urls") or {}
    reviews = (place or {}).get("reviews") or {}
    place_summary = ((place or {}).get("placeSummaries") or {}).get("summary")
    review_summary = (reviews or {}).get("reviewSummary")
    reuse_existing_description = existing_event is not None and place is None
    summary = str(
        requested.get("description")
        or place_summary
        or review_summary
        or (event_description(existing_event or {}) if reuse_existing_description else "")
        or _default_event_description(event_type, place_name, name)
    )
    tips = str(requested.get("notes") or _default_event_tips(event_type))
    cost = finite_float(requested.get("cost"), 0.0)

    base = {
        "event_id": existing_event.get("event_id") if existing_event else f"evt_{uuid.uuid4().hex}",
        "event_sort_key": sort_key,
        "day_number": day_number,
        "event_number": existing_event.get("event_number") if existing_event else next_legacy_event_number(events, day_number),
        "day_title": day_title(day_number, events),
        "date": day_date,
        "event_type": event_type,
        "is_locked": False,
    }
    if event_type in {"DINING", "ACTIVITY"}:
        base["place_details"] = {
            "event_name": name,
            "event_description": summary,
            "event_tips": tips,
            "place_name": place_name,
            "place_id": place_id,
            "address": address,
            "coordinates": coords,
            "summary": summary,
            "rating": finite_float(reviews.get("rating"), 0.0),
            "cost": cost,
            "start_time": format_dt(start),
            "end_time": format_dt(end),
            "durationMinutes": duration,
            "google_maps_url": urls.get("googleMapsUrl") or "",
            "website_url": urls.get("websiteUrl") or "",
        }
    else:
        base["other_details"] = {
            "event_name": name,
            "event_description": summary,
            "event_tips": tips,
            "place_name": place_name,
            "place_id": place_id,
            "address": address,
            "coordinates": coords,
            "summary": summary,
            "cost": cost,
            "start_time": format_dt(start),
            "end_time": format_dt(end),
            "durationMinutes": duration,
            "google_maps_url": urls.get("googleMapsUrl") or "",
            "website_url": urls.get("websiteUrl") or "",
        }
    return base


async def _maybe_add_commutes_around_event(events: list[dict[str, Any]], event: dict[str, Any]) -> list[dict[str, Any]]:
    result = canonicalize_events(events)
    current = event_by_id(result, str(event.get("event_id")))
    if current is None:
        return result
    before, after = _adjacent_regular_events(result, current)
    inserts: list[dict[str, Any]] = []
    if before and before.get("event_type") != "COMMUTE" and current.get("event_type") != "COMMUTE" and not events_same_location(before, current):
        commute_key = sort_key_between(before, current, float(current.get("event_sort_key") or 0) - 1)
        inserts.append(
            await _make_commute_event(
                events=[*result, *inserts],
                day_number=int(current["day_number"]),
                sort_key=commute_key,
                origin_event=before,
                destination_event=current,
            )
        )
    if after and after.get("event_type") != "COMMUTE" and current.get("event_type") != "COMMUTE" and not events_same_location(current, after):
        commute_key = sort_key_between(current, after, float(current.get("event_sort_key") or 0) + 1)
        inserts.append(
            await _make_commute_event(
                events=[*result, *inserts],
                day_number=int(current["day_number"]),
                sort_key=commute_key,
                origin_event=current,
                destination_event=after,
            )
        )
    if not inserts:
        return result
    return canonicalize_events([*result, *inserts])


async def _ensure_commutes_for_touched_days(
    events: list[dict[str, Any]],
    touched_days: set[int],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Add missing bridge commutes created by removals/moves on touched days."""
    result = canonicalize_events(events)
    added_ids: set[str] = set()
    natural_pairs = {("FLIGHT_TAKEOFF", "FLIGHT_LAND")}
    for day in sorted(touched_days):
        while True:
            inserted = False
            day_events = day_boundaries(result, day)
            for idx in range(1, len(day_events)):
                prev = day_events[idx - 1]
                curr = day_events[idx]
                if prev.get("event_type") == "COMMUTE" or curr.get("event_type") == "COMMUTE":
                    continue
                if (prev.get("event_type"), curr.get("event_type")) in natural_pairs:
                    continue
                if events_same_location(prev, curr):
                    continue
                commute_key = sort_key_between(prev, curr, float(curr.get("event_sort_key") or 0) - 1)
                commute = await _make_commute_event(
                    events=result,
                    day_number=day,
                    sort_key=commute_key,
                    origin_event=prev,
                    destination_event=curr,
                )
                result = canonicalize_events([*result, commute])
                added_ids.add(str(commute["event_id"]))
                inserted = True
                break
            if not inserted:
                break
    return result, added_ids


def _required_start_after_previous(day_events: list[dict[str, Any]], idx: int) -> Optional[datetime]:
    if idx <= 0:
        return None
    prev = day_events[idx - 1]
    if prev.get("event_type") == "COMMUTE" and idx >= 2:
        before_commute = day_events[idx - 2]
        base = event_end(before_commute)
        if base is None:
            return None
        duration = finite_float((prev.get("commute_details") or {}).get("durationSeconds"), 0.0)
        return base + timedelta(seconds=duration)
    return event_end(prev)


def _try_absorb_timing_deficit(
    events: list[dict[str, Any]],
    *,
    day_events: list[dict[str, Any]],
    blocker_idx: int,
    deficit: timedelta,
    min_sort_key: Optional[float],
) -> tuple[list[dict[str, Any]], set[str], bool]:
    """Shorten preceding flexible stops so a later locked/fixed event can stay put."""
    if deficit <= timedelta(0):
        return events, set(), True

    remaining_seconds = deficit.total_seconds()
    result = canonicalize_events(events)
    changed_ids: set[str] = set()
    min_duration_minutes = 20

    for candidate in reversed(day_events[:blocker_idx]):
        key = float(candidate.get("event_sort_key") or 0)
        if min_sort_key is not None and key < min_sort_key:
            continue
        event_id = str(candidate.get("event_id") or "")
        if not event_id or is_locked(candidate) or is_fixed_time_event(candidate):
            continue
        if candidate.get("event_type") not in FLEXIBLE_TIMED_TYPES:
            continue
        start = event_start(candidate)
        end = event_end(candidate)
        if start is None or end is None or end <= start:
            continue
        duration_seconds = (end - start).total_seconds()
        reducible_seconds = max(0.0, duration_seconds - (min_duration_minutes * 60))
        if reducible_seconds <= 0:
            continue

        reduce_by = min(reducible_seconds, remaining_seconds)
        new_end = end - timedelta(seconds=reduce_by)
        replacement = set_event_window(candidate, start, new_end)
        result = replace_event_by_id(result, event_id, replacement)
        changed_ids.add(event_id)
        remaining_seconds -= reduce_by
        if remaining_seconds <= 1:
            return canonicalize_events(result), changed_ids, True

    return canonicalize_events(result), changed_ids, False


def _repair_timing(
    events: list[dict[str, Any]],
    *,
    allowed_fixed_event_ids: set[str],
    touched_days: set[int],
    touched_event_ids: set[str],
) -> tuple[list[dict[str, Any]], Optional[str], set[str]]:
    result = canonicalize_events(events)
    changed_ids: set[str] = set()
    days = sorted({event.get("day_number") for event in result if isinstance(event.get("day_number"), int) and event.get("day_number") > 0})
    if touched_days:
        days = [day for day in days if int(day) in touched_days]
    for day in days:
        min_sort_key: Optional[float] = None
        for event in result:
            if event.get("day_number") != day or event.get("event_id") not in touched_event_ids:
                continue
            key = float(event.get("event_sort_key") or 0)
            min_sort_key = key if min_sort_key is None else min(min_sort_key, key)
        if min_sort_key is None:
            continue
        while True:
            changed = False
            day_events = day_boundaries(result, int(day))
            for idx, event in enumerate(day_events):
                if min_sort_key is not None and float(event.get("event_sort_key") or 0) < min_sort_key:
                    continue
                start = event_start(event)
                if start is None:
                    continue
                required = _required_start_after_previous(day_events, idx)
                if required is None or start >= required:
                    continue
                event_id = str(event.get("event_id"))
                if is_locked(event):
                    deficit = required - start
                    result, absorbed_ids, absorbed = _try_absorb_timing_deficit(
                        result,
                        day_events=day_events,
                        blocker_idx=idx,
                        deficit=deficit,
                        min_sort_key=min_sort_key,
                    )
                    changed_ids.update(absorbed_ids)
                    if absorbed:
                        changed = True
                        break
                    return result, f"Ripple would move locked event Day {day} event {event.get('event_number')} ({event_name(event)}).", changed_ids
                if is_fixed_time_event(event) and event_id not in allowed_fixed_event_ids:
                    deficit = required - start
                    result, absorbed_ids, absorbed = _try_absorb_timing_deficit(
                        result,
                        day_events=day_events,
                        blocker_idx=idx,
                        deficit=deficit,
                        min_sort_key=min_sort_key,
                    )
                    changed_ids.update(absorbed_ids)
                    if absorbed:
                        changed = True
                        break
                    return result, f"Ripple would move fixed-time event Day {day} event {event.get('event_number')} ({event_name(event)}).", changed_ids
                if not is_flexible_timed_event(event) and event_id not in allowed_fixed_event_ids:
                    return result, f"Ripple cannot safely move Day {day} event {event.get('event_number')} ({event_name(event)}).", changed_ids
                duration = event_duration_minutes(event)
                replacement = set_event_window(event, required, required + timedelta(minutes=duration))
                result = replace_event_by_id(result, event_id, replacement)
                changed_ids.add(event_id)
                changed = True
                break
            if not changed:
                break
    return canonicalize_events(result), None, changed_ids


def _has_concrete_detail_update(plan: dict[str, Any]) -> bool:
    requested = plan.get("requested_event") if isinstance(plan.get("requested_event"), dict) else {}
    updates = plan.get("detail_updates") if isinstance(plan.get("detail_updates"), dict) else {}
    for key in ("name", "notes", "description", "summary"):
        value = requested.get(key, updates.get(key))
        if isinstance(value, str) and value.strip():
            return True
    return requested.get("cost", updates.get("cost")) is not None


def _update_event_details(event: dict[str, Any], plan: dict[str, Any], user_message: str) -> dict[str, Any]:
    result = copy.deepcopy(event)
    requested = plan.get("requested_event") if isinstance(plan.get("requested_event"), dict) else {}
    updates = plan.get("detail_updates") if isinstance(plan.get("detail_updates"), dict) else {}
    field = detail_field_for_event(result)
    if not field:
        return result
    details = dict(result.get(field) or {})
    name = str(requested.get("name") or updates.get("name") or "").strip()
    notes = str(requested.get("notes") or updates.get("notes") or "").strip()
    cost = requested.get("cost", updates.get("cost"))

    if result.get("event_type") in {"DINING", "ACTIVITY"}:
        if name:
            details["event_name"] = name
            details["place_name"] = name
        if notes:
            details["event_tips"] = notes
        if cost is not None:
            details["cost"] = finite_float(cost, details.get("cost") or 0)
    elif result.get("event_type") == "OTHER":
        if name:
            details["event_name"] = name
            details["place_name"] = name
        if notes:
            details["event_tips"] = notes
        if cost is not None:
            details["cost"] = finite_float(cost, details.get("cost") or 0)
    elif result.get("event_type") in {"HOTEL_CHECKIN", "HOTEL_CHECKOUT"}:
        if name:
            details["hotel_name"] = name
        if notes:
            tip_key = "checkin_tips" if result.get("event_type") == "HOTEL_CHECKIN" else "checkout_tips"
            details[tip_key] = notes
    elif result.get("event_type") in {"CAR_PICKUP", "CAR_DROPOFF"}:
        if name:
            details["rental_company_name"] = name
        if notes:
            tip_key = "pickup_tips" if result.get("event_type") == "CAR_PICKUP" else "dropoff_tips"
            details[tip_key] = notes
    elif result.get("event_type") in {"FLIGHT_TAKEOFF", "FLIGHT_LAND"}:
        if name:
            details["flight_number"] = name
        if notes:
            tip_key = "takeoff_tips" if result.get("event_type") == "FLIGHT_TAKEOFF" else "landing_tips"
            details[tip_key] = notes

    result[field] = details
    return result


def _sync_adjacent_commutes_for_event(
    events: list[dict[str, Any]],
    event: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Keep unlocked commute card labels aligned after booking endpoint edits."""
    if event.get("event_type") not in BOOKING_PAIR_TYPES:
        return events, set()
    result = canonicalize_events(events)
    current = event_by_id(result, str(event.get("event_id")))
    if current is None:
        return result, set()

    before, after = _adjacent_regular_events(result, current)
    origin_coords, destination_coords = event_origin_dest(current)
    endpoint_name = event_location_name(current)
    changed: set[str] = set()

    def update_commute(commute: Optional[dict[str, Any]], endpoint: str) -> None:
        nonlocal result
        if not isinstance(commute, dict) or commute.get("event_type") != "COMMUTE" or is_locked(commute):
            return
        details = dict(commute.get("commute_details") or {})
        replacement = copy.deepcopy(commute)
        if endpoint == "destination":
            details["destinationName"] = endpoint_name
            if origin_coords:
                details["destination_coordinates"] = {"latitude": origin_coords[0], "longitude": origin_coords[1]}
        else:
            details["originName"] = endpoint_name
            if destination_coords:
                details["origin_coordinates"] = {"latitude": destination_coords[0], "longitude": destination_coords[1]}
        replacement["commute_details"] = details
        event_id = str(replacement.get("event_id"))
        result = replace_event_by_id(result, event_id, replacement)
        changed.add(event_id)

    update_commute(before, "destination")
    update_commute(after, "origin")
    return canonicalize_events(result), changed


async def _apply_plan(
    *,
    plan: dict[str, Any],
    events: list[dict[str, Any]],
    trip_input: dict[str, Any],
    attached_events: list[dict[str, Any]],
    user_message: str,
    chat_history: list,
) -> tuple[list[dict[str, Any]], set[str], set[str], set[int]]:
    action = _plan_action(plan)
    if action == "clarify":
        question = str(plan.get("clarify_question") or "Can you clarify what exactly you want me to change?")
        raise EditClarification(question)
    if action == "reject":
        reason = str(plan.get("rejection_reason") or "I cannot safely apply that edit to this itinerary.")
        raise EditRejected(reason)
    if action in {"remove", "replace", "move", "retime", "duration", "update_details"}:
        targets, question = _resolve_targets(
            plan=plan,
            events=events,
            attached_events=attached_events,
            user_message=user_message,
            chat_history=chat_history,
            required=True,
        )
        if question:
            raise EditClarification(question)
    else:
        targets = []

    changed_ids: set[str] = set()
    allowed_fixed_event_ids: set[str] = set()
    touched_days: set[int] = set()

    if action == "remove":
        expanded = _expand_booking_groups(events, targets)
        reason = _locked_target_reason(expanded)
        if reason:
            raise EditRejected(reason)
        touched_days.update(int(target["day_number"]) for target in expanded if isinstance(target.get("day_number"), int))
        candidate, removed_ids = _remove_with_commutes(events, expanded)
        changed_ids.update(removed_ids)
        for target in expanded:
            if is_fixed_time_event(target):
                allowed_fixed_event_ids.add(str(target["event_id"]))
        return candidate, changed_ids, allowed_fixed_event_ids, touched_days

    if action == "add":
        day, relation, reference, question = _resolve_placement(
            plan=plan,
            events=events,
            targets=[],
            user_message=user_message,
        )
        if question:
            raise EditClarification(question)
        requested = plan.get("requested_event") if isinstance(plan.get("requested_event"), dict) else {}
        requested_name = _clean_requested_event_name(
            str(requested.get("name") or _extract_requested_name(user_message, "add") or "").strip()
        )
        if _is_generic_requested_event(requested_name, user_message):
            raise EditClarification("What kind of stop should I add there?")
        sort_key = _sort_key_for_placement(events=events, day_number=day, relation=relation, reference=reference)
        displaced_commute_ids = _commutes_displaced_by_insertion(events, reference, relation)
        base_events = remove_event_ids(events, displaced_commute_ids) if displaced_commute_ids else events
        new_event = await _build_place_like_event(
            plan=plan,
            events=base_events,
            trip_input=trip_input,
            day_number=day,
            sort_key=sort_key,
            user_message=user_message,
            nearby_event=reference,
        )
        candidate = _insert_event(base_events, new_event)
        candidate = await _maybe_add_commutes_around_event(candidate, new_event)
        changed_ids.update(displaced_commute_ids)
        changed_ids.add(str(new_event["event_id"]))
        touched_days.add(day)
        return candidate, changed_ids, allowed_fixed_event_ids, touched_days

    if action == "replace":
        expanded = _expand_booking_groups(events, targets)
        reason = _locked_target_reason(expanded)
        if reason:
            raise EditRejected(reason)
        if len(expanded) > 1 and any(event.get("event_type") in BOOKING_PAIR_TYPES for event in expanded):
            candidate = events
            for member in expanded:
                replacement = _update_event_details(member, plan, user_message)
                candidate = replace_event_by_id(candidate, str(member["event_id"]), replacement)
                candidate, commute_changed = _sync_adjacent_commutes_for_event(candidate, replacement)
                changed_ids.add(str(member["event_id"]))
                changed_ids.update(commute_changed)
                allowed_fixed_event_ids.add(str(member["event_id"]))
                if isinstance(member.get("day_number"), int):
                    touched_days.add(int(member["day_number"]))
            return candidate, changed_ids, allowed_fixed_event_ids, touched_days

        target = expanded[0]
        if target.get("event_type") not in FLEXIBLE_TIMED_TYPES:
            raise EditRejected("I can only replace flexible activity, dining, or other events safely right now. Locked and fixed booking replacements need exact booking details.")
        candidate, removed = _remove_with_commutes(events, [target])
        sort_key = float(target.get("event_sort_key") or SORT_STEP)
        replacement = await _build_place_like_event(
            plan=plan,
            events=candidate,
            trip_input=trip_input,
            day_number=int(target["day_number"]),
            sort_key=sort_key,
            user_message=user_message,
            existing_event=target,
            nearby_event=target,
            require_real_place=True,
        )
        candidate = _insert_event(candidate, replacement)
        candidate = await _maybe_add_commutes_around_event(candidate, replacement)
        changed_ids.update(removed)
        changed_ids.add(str(replacement["event_id"]))
        if isinstance(target.get("day_number"), int):
            touched_days.add(int(target["day_number"]))
        return candidate, changed_ids, allowed_fixed_event_ids, touched_days

    if action == "update_details":
        expanded = _expand_booking_groups(events, targets)
        reason = _locked_target_reason(expanded)
        if reason:
            raise EditRejected(reason)
        if not _has_concrete_detail_update(plan):
            raise EditClarification("What exact detail should I change for that event?")
        candidate = events
        for target in expanded:
            replacement = _update_event_details(target, plan, user_message)
            candidate = replace_event_by_id(candidate, str(target["event_id"]), replacement)
            candidate, commute_changed = _sync_adjacent_commutes_for_event(candidate, replacement)
            changed_ids.add(str(target["event_id"]))
            changed_ids.update(commute_changed)
            if is_fixed_time_event(target):
                allowed_fixed_event_ids.add(str(target["event_id"]))
            if isinstance(target.get("day_number"), int):
                touched_days.add(int(target["day_number"]))
        return candidate, changed_ids, allowed_fixed_event_ids, touched_days

    if action in {"retime", "duration"}:
        if len(targets) != 1:
            raise EditClarification("Which single event should I retime?")
        target = targets[0]
        if is_locked(target):
            raise EditRejected(f"I cannot retime locked event Day {target.get('day_number')} event {target.get('event_number')} ({event_name(target)}).")
        if is_fixed_time_event(target):
            raise EditRejected("I cannot safely retime fixed booking events like flights, hotels, or rental cars from chat unless that booking itself is changed.")
        if target.get("event_type") not in FLEXIBLE_TIMED_TYPES:
            raise EditRejected("I can only retime flexible activity, dining, or other events.")

        start = event_start(target)
        end = event_end(target)
        if start is None or end is None:
            raise EditRejected("That event does not have editable start/end times.")
        duration = event_duration_minutes(target)
        if action == "duration":
            duration = int(plan.get("duration_minutes") or _extract_duration_minutes(user_message) or duration)
            new_start = start
            new_end = start + timedelta(minutes=duration)
        else:
            day_date = target.get("date") or date_for_day(trip_input, int(target["day_number"]))
            new_start = _parse_requested_datetime(plan.get("new_start_time") or _extract_time_text(user_message), day_date)
            if new_start is None:
                raise EditClarification("What time should this event start?")
            new_end = new_start + timedelta(minutes=duration)
        replacement = set_event_window(target, new_start, new_end)
        candidate = replace_event_by_id(events, str(target["event_id"]), replacement)
        changed_ids.add(str(target["event_id"]))
        touched_days.add(int(target["day_number"]))
        return candidate, changed_ids, allowed_fixed_event_ids, touched_days

    if action == "move":
        if len(targets) != 1:
            raise EditClarification("Which single event should I move?")
        target = targets[0]
        if is_locked(target):
            raise EditRejected(f"I cannot move locked event Day {target.get('day_number')} event {target.get('event_number')} ({event_name(target)}).")
        if is_fixed_time_event(target):
            raise EditRejected("I cannot safely move fixed booking events like flights, hotels, or rental cars from chat.")
        day, relation, reference, question = _resolve_placement(
            plan=plan,
            events=events,
            targets=targets,
            user_message=user_message,
        )
        if question:
            raise EditClarification(question)
        candidate, removed = _remove_with_commutes(events, [target])
        sort_key = _sort_key_for_placement(events=candidate, day_number=day, relation=relation, reference=reference)
        replacement = copy.deepcopy(target)
        replacement["day_number"] = day
        if target.get("day_number") != day:
            replacement["event_number"] = next_legacy_event_number(candidate, day)
        replacement["event_sort_key"] = sort_key
        replacement["day_title"] = day_title(day, candidate)
        replacement["date"] = date_for_day(trip_input, day) or replacement.get("date")
        if target.get("event_type") in FLEXIBLE_TIMED_TYPES:
            start = event_start(target)
            if start:
                new_date = datetime.fromisoformat(replacement["date"]).date()
                new_start = datetime.combine(new_date, start.time())
                replacement = set_event_window(replacement, new_start, new_start + timedelta(minutes=event_duration_minutes(target)))
        candidate = _insert_event(candidate, replacement)
        candidate = await _maybe_add_commutes_around_event(candidate, replacement)
        changed_ids.update(removed)
        changed_ids.add(str(target["event_id"]))
        if isinstance(target.get("day_number"), int):
            touched_days.add(int(target["day_number"]))
        touched_days.add(day)
        return candidate, changed_ids, allowed_fixed_event_ids, touched_days

    raise EditClarification("Can you clarify the edit you want?")


async def run_edit_engine(state: EditorState) -> EditOutcome:
    events = canonicalize_events(state.get("current_itinerary_events") or [])
    trip_input = dict(state.get("trip_input") or {})
    raw_user_message = state.get("user_message", "")
    user_message = _last_clarified_edit_message(raw_user_message, list(state.get("chat_history") or []))
    attached_events = list(state.get("attached_events") or [])

    plan = await _llm_edit_plan(
        user_message=user_message,
        chat_history=list(state.get("chat_history") or []),
        events=events,
        attached_events=attached_events,
        trip_input=trip_input,
        use_fast_model=bool(state.get("use_fast_model", False)),
    )
    fallback = _fallback_plan(message=user_message, attached_events=attached_events)
    if not plan:
        plan = fallback
    elif _should_use_fallback_plan(
        llm_plan=plan,
        fallback_plan=fallback,
        user_message=user_message,
        attached_events=attached_events,
    ):
        # Deterministic UI context and explicit references beat an over-cautious
        # or refusal-prone planner. Locked/fixed/structural guards still run in
        # _apply_plan and validate_candidate.
        plan = fallback
    elif _plan_action(plan) == "update_details" and _message_requests_duration(user_message):
        plan = dict(plan)
        plan["action"] = "duration"
        plan["duration_minutes"] = _extract_duration_minutes(user_message)
    plan = _augment_plan_from_chat_history(
        plan=plan,
        events=events,
        chat_history=list(state.get("chat_history") or []),
        user_message=user_message,
    )
    if _plan_action(plan) == "update_details" and _message_requests_venue_replacement(user_message, plan):
        plan = dict(plan)
        plan["action"] = "replace"

    try:
        candidate, changed_ids, allowed_fixed_ids, touched_days = await _apply_plan(
            plan=plan,
            events=events,
            trip_input=trip_input,
            attached_events=attached_events,
            user_message=user_message,
            chat_history=list(state.get("chat_history") or []),
        )
        candidate, added_commute_ids = await _ensure_commutes_for_touched_days(candidate, touched_days)
        changed_ids.update(added_commute_ids)
        candidate, ripple_error, ripple_changed = _repair_timing(
            candidate,
            allowed_fixed_event_ids=allowed_fixed_ids,
            touched_days=touched_days,
            touched_event_ids=changed_ids,
        )
        changed_ids.update(ripple_changed)
        if ripple_error:
            return EditOutcome(
                status="rejected",
                reason=ripple_error,
                plan=plan,
            )

        if events_hash(candidate) == events_hash(events):
            return EditOutcome(
                status="clarify",
                question=(
                    "I could not identify a concrete itinerary change from that request. "
                    "Please name the event and the exact change you want."
                ),
                plan=plan,
            )

        preferences = trip_input.get("preferences") or {}
        validation = validate_candidate(
            base_events=events,
            candidate_events=candidate,
            changed_event_ids=changed_ids,
            changed_day_numbers=touched_days,
            allowed_fixed_event_ids=allowed_fixed_ids,
            smart_anchors=state.get("smart_anchors") or trip_input.get("smart_anchors") or [],
            locked_routines=preferences.get("locked_routines") or [],
            trip_start=trip_input.get("start_date") or {},
        )
        if not validation.ok:
            return EditOutcome(
                status="rejected",
                reason="I could not apply that edit without breaking the itinerary.",
                validation_errors=validation.errors[:12],
                plan=plan,
            )

        async with Session() as db:
            commit = await commit_candidate(
                db,
                trip_id=str(state.get("trip_id")),
                candidate_events=candidate,
                base_snapshot_cursor=state.get("snapshot_cursor"),
                base_events_hash=state.get("base_events_hash") or events_hash(events),
                description=user_message,
            )
        return EditOutcome(
            status="committed",
            summary=_summarize_commit(plan, commit, changed_ids),
            commit=commit,
            plan=plan,
        )
    except EditClarification as exc:
        return EditOutcome(status="clarify", question=str(exc), plan=plan)
    except EditRejected as exc:
        return EditOutcome(status="rejected", reason=str(exc), plan=plan)
    except EditConflictError as exc:
        return EditOutcome(status="conflict", reason=str(exc), plan=plan)
    except Exception as exc:
        log.exception("Edit engine failed", error=str(exc))
        return EditOutcome(status="failed", reason=f"Editing failed: {exc}", plan=plan)


def _summarize_commit(plan: dict[str, Any], commit: CommitResult, changed_ids: set[str]) -> str:
    action = _plan_action(plan)
    count = len(changed_ids)
    cost = sum_chargeable_cost_usd(commit.events)
    verbs = {
        "add": "added that to the itinerary",
        "remove": "removed that from the itinerary",
        "replace": "updated that part of the itinerary",
        "move": "moved that part of the itinerary",
        "retime": "updated the timing",
        "duration": "updated the duration",
        "update_details": "updated the details",
    }
    action_text = verbs.get(action, "updated the itinerary")
    item_label = "item" if count == 1 else "items"
    return (
        f"I {action_text}. Updated {count} {item_label}. "
        f"Current trip estimate is ${cost:.2f}."
    )
