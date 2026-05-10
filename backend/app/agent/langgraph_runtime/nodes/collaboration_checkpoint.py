"""
Collaboration checkpoint node.

Autonomous mode: pure pass-through.

Collaborative mode: runs a small, fast LLM call to produce ONE seed question
tailored to THIS trip's actual context (research_facts, journey, trip_input,
preferences). Avoids hard-coded "what's the vibe" boilerplate that feels
canned across every generation.

The seed answer is threaded into every day_planner invocation via
state["collab_seed_answer"] under a clearly-labelled "USER VIBE PREFERENCE"
block (so the prompt-injection wrapper still scopes it as preference data,
never instructions).

Resume runs (is_resuming=True) skip this checkpoint — the seed has either
already been collected on the original session OR the user is resuming a
mid-trip plan and re-asking would be obnoxious.
"""
import json
import re
import os
import uuid
from typing import Any, Dict, Optional

from app.agent.llm import litellm_types as types
from app.core.config import settings
from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.collaboration import (
    ask_user_directly,
    validate_question_args,
)
from app.agent.langgraph_runtime.output_style import with_user_facing_output_policy
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.schemas.structuredInput import TripInput
from app.agent.helpers.qa_persistence import persist_qa_entry
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_llm_model_sku

log = get_agent_logger("nodes.collaboration_checkpoint")
PLANNER_MODEL_SKU = resolve_llm_model_sku(settings.PLANNER_AGENT_MODEL)


# Fallback seed question if the LLM fails or its output is malformed.
# Generic enough to apply to any trip; only used when the LLM call breaks.
_FALLBACK_QUESTION = "Anything in particular you want me to lean into for this trip?"
_FALLBACK_OPTIONS = [
    "Hidden gems",
    "Big-ticket icons",
    "A mix",
    "Surprise me",
]

collaboration_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "collaborationPrompt.md"
)
with open(collaboration_PROMPT_PATH, "r", encoding="utf-8") as _f:
    COLLABORATION_SYSTEM_PROMPT = _f.read()

def _trim(s: Optional[str], n: int) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    return s if len(s) <= n else s[:n] + "…"


def _build_seed_question_user_message(
    trip_data: TripInput,
    research_facts: dict,
    journey: list,
) -> str:
    """Pack the trip context into a compact prompt body for the seed-question LLM."""
    origin_label = getattr(getattr(trip_data, "origin", None), "city", None) or "Origin"
    dests = []
    try:
        for d in (trip_data.destinations or []):
            label = getattr(d, "city", None) or getattr(d, "name", None) or str(d)
            if label:
                dests.append(label)
    except Exception:
        dests = list(journey) if journey else []
    if not dests and journey:
        dests = list(journey)

    body = {
        "origin": origin_label,
        "destinations": dests,
        "journey": list(journey) if journey else [],
        "start_date": _trim(getattr(trip_data.start_date, "localTimeString", None), 32),
        "end_date": _trim(getattr(trip_data.end_date, "localTimeString", None), 32),
        "pace": getattr(trip_data, "pace", None),
        "budget": getattr(trip_data, "budget", None),
        "adults": getattr(trip_data, "adults", None),
        "children": getattr(trip_data, "children", None),
        "travel_mode": getattr(trip_data, "routing_style", None),
        "preferences": getattr(trip_data, "preferences", None) or {},
        "user_textual_context": _trim(getattr(trip_data, "textualContext", None), 400),
        "research_facts": research_facts or {},
    }
    return (
        "Generate the seed question for this trip. Trip context (JSON):\n\n"
        f"{json.dumps(body, default=str)}"
    )


def _parse_seed_question_json(text: Optional[str]) -> Optional[dict]:
    """Best-effort extraction of the JSON object from the LLM's reply."""
    if not text:
        return None
    s = text.strip()
    # Strip code fences.
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    # Grab the first {...} block.
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(s[start : end + 1])
    except Exception:
        return None


async def _generate_seed_question(state: PlannerState) -> dict:
    """
    Ask the small LLM to produce ONE seed question for THIS trip.

    Returns a dict ``{question, options, answer_type, skippable}`` ready to
    pass to ask_user_directly. Falls back to a generic question on any
    failure so the user still gets a chance to weigh in.
    """
    fallback = {
        "question": _FALLBACK_QUESTION,
        "options": list(_FALLBACK_OPTIONS),
        "answer_type": "single",
        "skippable": True,
    }

    if runtime.model_client is None:
        log.warning("LLM client unavailable; using fallback seed question.")
        return fallback

    try:
        trip_data = TripInput(**(state.get("trip_input") or {}))
    except Exception as exc:
        log.warning("Could not parse trip_input for seed question; using fallback", error=str(exc))
        return fallback

    research_facts = state.get("research_facts") or {}
    journey = list(state.get("journey") or [])

    use_fast_model = bool(state.get("use_fast_model", False))
    _collab_model, _ = settings.get_planner_agent_model(use_fast_model)
    _collab_sku = resolve_llm_model_sku(_collab_model)

    try:
        await get_rate_limiter().consume(_collab_sku)
    except RateLimitExceeded as exc:
        log.warning(
            "Planner model quota exhausted for seed question; using fallback",
            sku=exc.sku,
            retry_after=exc.retry_after_seconds,
        )
        return fallback

    user_msg = _build_seed_question_user_message(trip_data, research_facts, journey)

    try:
        resp = await runtime.model_client.aio.models.generate_content(
            model=_collab_model,
            contents=[user_msg],
            config=with_user_facing_output_policy(
                types.GenerateContentConfig(
                    system_instruction=COLLABORATION_SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=512,
                )
            ),
        )
    except Exception as exc:
        log.warning("Seed-question LLM call failed; using fallback", error=str(exc))
        return fallback

    parsed = _parse_seed_question_json(getattr(resp, "text", None))
    if not parsed:
        log.warning("Seed-question LLM returned unparseable output; using fallback")
        return fallback

    # Coerce + validate via the same gate the chat-loop tool branch uses,
    # so the seed question matches the chip / answer_type contract the UI
    # already knows how to render.
    parsed.setdefault("skippable", True)
    if "options" in parsed and isinstance(parsed["options"], list):
        # Drop empties / dupes / overlong.
        seen = set()
        cleaned = []
        for opt in parsed["options"]:
            if not isinstance(opt, str):
                continue
            o = opt.strip()
            if not o or o.lower() in seen:
                continue
            seen.add(o.lower())
            cleaned.append(o[:40])
            if len(cleaned) == 4:
                break
        parsed["options"] = cleaned

    if validate_question_args(parsed) is not None:
        log.warning(
            "Seed-question failed validation; using fallback",
            attempted=parsed,
        )
        return fallback

    return {
        "question": parsed["question"],
        "options": list(parsed["options"]),
        "answer_type": parsed.get("answer_type", "single"),
        "skippable": bool(parsed.get("skippable", True)),
    }


async def collaboration_checkpoint_node(state: PlannerState) -> Dict[str, Any]:
    if state.get("mode") != "collaborative":
        return {}
    if state.get("is_resuming"):
        return {}
    if state.get("collab_seed_answered"):
        return {}

    trip_id = state.get("trip_id")
    if not trip_id:
        log.warning("Collaboration checkpoint skipped: no trip_id in state")
        return {"collab_seed_answered": True}

    run_id = (str(trip_id) + "-" + (state.get("user_id") or "")) or str(uuid.uuid4())
    set_agent_log_context(run_id=run_id, node="collaboration_checkpoint", day=0)

    log.info("Generating seed question via LLM", trip_id=trip_id)
    q = await _generate_seed_question(state)
    log.info("Seed question generated")

    result = await ask_user_directly(
        trip_id=str(trip_id),
        question=q["question"],
        options=q["options"],
        answer_type=q["answer_type"],
        skippable=q["skippable"],
    )

    if result.get("cancelled"):
        log.info("Seed question cancelled by user")
        return {"cancelled": True, "collab_seed_answered": True}

    skipped = bool(result.get("skipped"))
    if skipped:
        answer_text = "(no preference — surprise me)"
    else:
        answer_text = result.get("answer") or "(no preference — surprise me)"

    log.info("Seed answer received")

    user_id = state.get("user_id")
    if trip_id and user_id:
        await persist_qa_entry(
            trip_id=str(trip_id),
            user_id=str(user_id),
            qa_entry={
                "call_id": result.get("call_id", ""),
                "question": q["question"],
                "options": q["options"],
                "answer_type": q["answer_type"],
                "skippable": q["skippable"],
                "answer": answer_text,
                "skipped": skipped,
                "context": "seed",
            },
        )

    return {
        "collab_seed_answer": answer_text,
        "collab_seed_answered": True,
    }
