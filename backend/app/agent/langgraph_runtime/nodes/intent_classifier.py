"""Intent classifier node for editor graph."""

import json
import os
import re
from typing import Any, Dict, Optional

from app.agent.llm import litellm_types as types
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.streaming import emit
from app.core.config import settings
from app.logging import get_agent_logger
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_llm_model_sku

log = get_agent_logger("intent_classifier")
EDITOR_MODEL_SKU = resolve_llm_model_sku(settings.EDITOR_AGENT_MODEL)

_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "editor", "intentClassifierPrompt.md"
)
with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    INTENT_SYSTEM_PROMPT = _f.read()


def _extract_json(text: Optional[str]) -> Optional[dict]:
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    start = s.find("{")
    end = s.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(s[start : end + 1])
    except Exception:
        return None


def _compact_itinerary(events: list[dict]) -> list[dict]:
    compact = []
    for e in events or []:
        compact.append(
            {
                "day_number": e.get("day_number"),
                "event_number": e.get("event_number"),
                "event_type": e.get("event_type"),
                "day_title": e.get("day_title"),
            }
        )
    return compact


_EDIT_HINT_RE = re.compile(
    r"\b(add|remove|delete|cancel|change|replace|swap|move|update|shorten|lengthen|book|switch|use|pick)\b",
    re.IGNORECASE,
)
_ITINERARY_HINT_RE = re.compile(
    r"\b(itinerary|trip|plan|schedule|day|event|hotel|flight|restaurant|dinner|lunch|breakfast|coffee|activity|booking|commute|visit|reservation|suggest|recommend|option|options|alternatives|near|nearby|this|that|there|where|when|what time)\b",
    re.IGNORECASE,
)
_SIMPLE_CHAT_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|thanks|thank you|good morning|good afternoon|good evening)[!. ]*\s*$",
    re.IGNORECASE,
)
_NEW_TRIP_REQUEST_RE = re.compile(
    r"\b(new|another|fresh)\s+(trip|itinerary|plan)\b|\b(create|start|draft|plan)\s+(a\s+)?(new|another|fresh)\b",
    re.IGNORECASE,
)
_MUTATION_PHRASE_RE = re.compile(
    r"\b("
    r"make|spend|skip|avoid|prefer|instead|less|more|earlier|later|delay|reschedule|retime|"
    r"duration|minutes?|hours?|put|insert|drop|extend|reduce|increase"
    r")\b",
    re.IGNORECASE,
)
_SUGGESTION_REQUEST_RE = re.compile(
    r"\b("
    r"suggest|recommend|recommendations|options|alternatives|ideas|what are some|show me|find me|look for"
    r")\b",
    re.IGNORECASE,
)
_APPLY_OPTION_RE = re.compile(
    r"\b("
    r"use|pick|select|choose|replace|swap|switch|change"
    r")\b.*\b(?:option\s*)?\d+\b|\b(?:go with|use|pick|select|choose)\b",
    re.IGNORECASE,
)
_CLARIFICATION_MARKER_RE = re.compile(
    r"\b(can you clarify|which event|which single event|which trip day|which day|what time|which one|which place|should i edit|should i place)\b",
    re.IGNORECASE,
)
_FOLLOWUP_CONTEXT_RE = re.compile(
    r"\b(it|this|that|there|those|them|same|more options|more recommendations|other options|alternatives|option\s*\d+)\b",
    re.IGNORECASE,
)


def _looks_like_current_itinerary_edit(user_message: str, attached_events: list) -> bool:
    if _NEW_TRIP_REQUEST_RE.search(user_message or ""):
        return False
    if _SUGGESTION_REQUEST_RE.search(user_message or "") and not _APPLY_OPTION_RE.search(user_message or ""):
        return False
    return bool(
        (_EDIT_HINT_RE.search(user_message or "") or _MUTATION_PHRASE_RE.search(user_message or ""))
        and (attached_events or _ITINERARY_HINT_RE.search(user_message or ""))
    )


def _looks_like_clarification_followup(user_message: str, chat_history: list) -> bool:
    if not chat_history:
        return False
    last_assistant = ""
    for item in reversed(chat_history):
        if isinstance(item, dict) and item.get("role") == "assistant":
            last_assistant = str(item.get("content") or "")
            break
    if not last_assistant or not _CLARIFICATION_MARKER_RE.search(last_assistant):
        return False
    return bool(
        re.search(r"\bday\s*#?\s*\d+\b|\bevent\s*#?\s*\d+\b|\b\d{1,2}(:\d{2})?\s*(am|pm)\b", user_message or "", re.IGNORECASE)
        or len((user_message or "").strip()) <= 80
    )


def _chat_history_has_itinerary_context(chat_history: list) -> bool:
    for item in reversed(chat_history or []):
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        if _ITINERARY_HINT_RE.search(content):
            return True
    return False


def _fallback_needs_context(
    *,
    user_message: str,
    intent: str,
    attached_events: list,
    chat_history: list,
) -> bool:
    if attached_events:
        return True
    if intent == "edit":
        return True
    if _SIMPLE_CHAT_RE.match(user_message or ""):
        return False
    if _FOLLOWUP_CONTEXT_RE.search(user_message or ""):
        if _chat_history_has_itinerary_context(chat_history):
            return True
    return bool(_ITINERARY_HINT_RE.search(user_message or ""))


async def intent_classifier_node(state: EditorState) -> Dict[str, Any]:
    user_message = state.get("user_message", "")
    chat_history = list(state.get("chat_history") or [])[-6:]
    attached_events = list(state.get("attached_events") or [])
    current_events = list(
        state.get("current_itinerary_events")
        or state.get("cached_itinerary_events")
        or []
    )

    attached_summary = []
    for item in attached_events:
        event_data = item.get("event_data") if isinstance(item, dict) else None
        attached_summary.append(
            {
                "day_number": item.get("day_number") if isinstance(item, dict) else None,
                "event_number": item.get("event_number") if isinstance(item, dict) else None,
                "event_type": (event_data or {}).get("event_type"),
            }
        )

    prompt_body = {
        "user_message": user_message,
        "chat_history": chat_history,
        "attached_events": attached_summary,
        "itinerary_summary": _compact_itinerary(current_events),
    }

    try:
        await get_rate_limiter().consume(EDITOR_MODEL_SKU)
    except RateLimitExceeded as exc:
        log.error("Conversation model quota exhausted", sku=exc.sku, retry_after=exc.retry_after_seconds)
        intent = "conversation"
        needs_itinerary_context = _fallback_needs_context(
            user_message=user_message,
            intent=intent,
            attached_events=attached_events,
            chat_history=chat_history,
        )
        emit({"type": "intent", "value": intent})
        return {
            "intent": intent,
            "needs_itinerary_context": needs_itinerary_context,
        }

    try:
        if runtime.model_client is None:
            raise RuntimeError("LLM client not ready")
        resp = await runtime.model_client.aio.models.generate_content(
            model=settings.EDITOR_AGENT_MODEL,
            contents=[json.dumps(prompt_body, default=str)],
            config=types.GenerateContentConfig(
                system_instruction=INTENT_SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        parsed = _extract_json(getattr(resp, "text", None)) or {}
        intent = parsed.get("intent")
        if intent not in ("conversation", "edit"):
            intent = "conversation"
        clarification_followup = _looks_like_clarification_followup(user_message, chat_history)
        apply_option_followup = bool(
            _APPLY_OPTION_RE.search(user_message or "")
            and _FOLLOWUP_CONTEXT_RE.search(user_message or "")
            and _chat_history_has_itinerary_context(chat_history)
        )
        forced_edit = (intent == "conversation" and _looks_like_current_itinerary_edit(
            user_message,
            attached_events,
        )) or apply_option_followup
        fallback_needs_context = _fallback_needs_context(
            user_message=user_message,
            intent=intent,
            attached_events=attached_events,
            chat_history=chat_history,
        )
        if forced_edit or clarification_followup:
            intent = "edit"
        needs_itinerary_context = parsed.get("needs_itinerary_context")
        if forced_edit or clarification_followup:
            needs_itinerary_context = True
        elif not isinstance(needs_itinerary_context, bool):
            needs_itinerary_context = fallback_needs_context
        elif fallback_needs_context:
            needs_itinerary_context = True
    except Exception as exc:
        log.warning("Intent classifier failed; defaulting to conversation", error=str(exc))
        intent = "edit" if _EDIT_HINT_RE.search(user_message or "") else "conversation"
        if _SUGGESTION_REQUEST_RE.search(user_message or "") and not _APPLY_OPTION_RE.search(user_message or ""):
            intent = "conversation"
        needs_itinerary_context = _fallback_needs_context(
            user_message=user_message,
            intent=intent,
            attached_events=attached_events,
            chat_history=chat_history,
        )

    emit({"type": "intent", "value": intent})
    return {
        "intent": intent,
        "needs_itinerary_context": needs_itinerary_context,
    }
