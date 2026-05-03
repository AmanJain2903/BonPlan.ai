"""Intent classifier node for editor graph."""

import json
import os
import re
from typing import Any, Dict, Optional

from google import genai
from google.genai import types

from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.streaming import emit
from app.core.config import settings
from app.logging import get_agent_logger
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_gemini_model_sku

log = get_agent_logger("intent_classifier")
CONVERSATION_MODEL_SKU = resolve_gemini_model_sku(settings.CONVERSATION_AGENT_MODEL)

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
    r"\b(itinerary|trip|plan|schedule|day|event|hotel|flight|restaurant|dinner|lunch|breakfast|coffee|activity|booking|commute|visit|reservation|suggest|recommend|near|nearby|this|that|there|where|when|what time)\b",
    re.IGNORECASE,
)
_SIMPLE_CHAT_RE = re.compile(
    r"^\s*(hi|hey|hello|yo|thanks|thank you|good morning|good afternoon|good evening)[!. ]*\s*$",
    re.IGNORECASE,
)


def _fallback_needs_context(
    *,
    user_message: str,
    intent: str,
    attached_events: list,
) -> bool:
    if attached_events:
        return True
    if intent == "edit":
        return True
    if _SIMPLE_CHAT_RE.match(user_message or ""):
        return False
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
        await get_rate_limiter().consume(CONVERSATION_MODEL_SKU)
    except RateLimitExceeded as exc:
        log.error("Conversation model quota exhausted", sku=exc.sku, retry_after=exc.retry_after_seconds)
        intent = "conversation"
        needs_itinerary_context = _fallback_needs_context(
            user_message=user_message,
            intent=intent,
            attached_events=attached_events,
        )
        emit({"type": "intent", "value": intent})
        return {
            "intent": intent,
            "needs_itinerary_context": needs_itinerary_context,
        }

    try:
        client = genai.Client(api_key=settings.CONVERSATION_AGENT_API_KEY)
        resp = await client.aio.models.generate_content(
            model=settings.CONVERSATION_AGENT_MODEL,
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
        needs_itinerary_context = parsed.get("needs_itinerary_context")
        if not isinstance(needs_itinerary_context, bool):
            needs_itinerary_context = _fallback_needs_context(
                user_message=user_message,
                intent=intent,
                attached_events=attached_events,
            )
    except Exception as exc:
        log.warning("Intent classifier failed; defaulting to conversation", error=str(exc))
        intent = "edit" if _EDIT_HINT_RE.search(user_message or "") else "conversation"
        needs_itinerary_context = _fallback_needs_context(
            user_message=user_message,
            intent=intent,
            attached_events=attached_events,
        )

    emit({"type": "intent", "value": intent})
    return {
        "intent": intent,
        "needs_itinerary_context": needs_itinerary_context,
    }
