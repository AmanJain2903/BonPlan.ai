"""Structural-change classifier for editor graph."""

import json
import os
from typing import Any, Dict, Optional

from app.agent.llm import litellm_types as types
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.streaming import emit
from app.core.config import settings
from app.logging import get_agent_logger
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_llm_model_sku

log = get_agent_logger("structural_classifier")
EDITOR_MODEL_SKU = resolve_llm_model_sku(settings.EDITOR_AGENT_MODEL)

_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "editor", "structuralClassifierPrompt.md"
)
with open(_PROMPT_PATH, "r", encoding="utf-8") as _f:
    STRUCTURAL_SYSTEM_PROMPT = _f.read()


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


async def structural_classifier_node(state: EditorState) -> Dict[str, Any]:
    user_message = state.get("user_message", "")
    trip_input = state.get("trip_input") or {}

    prompt_body = {
        "user_message": user_message,
        "trip_input": trip_input,
    }

    try:
        await get_rate_limiter().consume(EDITOR_MODEL_SKU)
    except RateLimitExceeded:
        return {"is_structural_change": False, "structural_reason": ""}

    try:
        if runtime.model_client is None:
            raise RuntimeError("LLM client not ready")
        resp = await runtime.model_client.aio.models.generate_content(
            model=settings.EDITOR_AGENT_MODEL,
            contents=[json.dumps(prompt_body, default=str)],
            config=types.GenerateContentConfig(
                system_instruction=STRUCTURAL_SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        parsed = _extract_json(getattr(resp, "text", None)) or {}
        is_structural = bool(parsed.get("is_structural", False))
        reason = str(parsed.get("reason") or "")
    except Exception as exc:
        log.warning("Structural classifier failed; defaulting to non-structural", error=str(exc))
        is_structural = False
        reason = ""

    conversation_notes = ""
    if is_structural:
        conversation_notes = (
            "That change cannot be applied inside this itinerary chat."
            " I can only answer questions about this current itinerary or make event-level edits to it."
        )
        emit({"type": "structural_change", "reason": reason or "trip structure"})

    return {
        "is_structural_change": is_structural,
        "structural_reason": reason,
        "conversation_notes": conversation_notes,
    }
