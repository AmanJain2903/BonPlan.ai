"""
Research-and-start node.

Runs a focused chat loop that:
  1. Does light destination research (1-2 web searches, weather, geography)
  2. Emits the START event (day_number=0)
  3. Produces a compact research_facts JSON (≤ 2 KB) for downstream day nodes

The loop uses stop_after_start=True so it terminates as soon as START is emitted
rather than waiting for END.  The final model text (after START) is parsed as
research_facts JSON; on failure an empty dict is used.
"""
import json
import os
import uuid
from typing import Any, Dict, Optional

from google.genai import types

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.gemini_adapter import run_chat_loop
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.streaming import emit
from app.agent.schemas.structuredInput import TripInput

log = get_agent_logger("research")

_RESEARCH_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "researchPrompt.md"
)
with open(_RESEARCH_PROMPT_PATH, "r", encoding="utf-8") as _f:
    RESEARCH_SYSTEM_PROMPT = _f.read()

_RESEARCH_FACTS_SIZE_LIMIT = 2048  # bytes


async def _truncate_research_facts(facts: dict) -> dict:
    raw = json.dumps(facts, default=str)
    if len(raw.encode()) <= _RESEARCH_FACTS_SIZE_LIMIT:
        return facts
    for k, v in list(facts.items()):
        if isinstance(v, str) and len(v) > 200:
            facts[k] = v[:200] + "…"
    raw = json.dumps(facts, default=str)
    if len(raw.encode()) > _RESEARCH_FACTS_SIZE_LIMIT:
        log.warning("Research facts still too big. Returning anyways")
    return facts

async def _parse_llm_research_json(text: Optional[str]) -> dict:
    """Best-effort JSON extraction from the LLM's post-START output."""
    if not text:
        return {}
    s = text.strip()
    # Strip common markdown fences.
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
    # Grab the first {...} object.
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(s[start : end + 1])
    except Exception:
        log.warning("Failed to parse LLM research JSON. Returning empty dict.")
        return {}

async def research_node(state: PlannerState) -> Dict[str, Any]:
    run_id = (state.get("trip_id") + "-" + state.get("user_id")) if state.get("user_id") and state.get("trip_id") else str(uuid.uuid4())
    set_agent_log_context(run_id=run_id, node="research", day=0)

    trip_payload = state.get("trip_input", {})
    trip_data = TripInput(**trip_payload)

    config = types.GenerateContentConfig(
        tools=[runtime.research_tool_block or runtime.planner_tool_block],
        system_instruction=RESEARCH_SYSTEM_PROMPT,
        temperature=0.5,
        # Research output = START event + one compact JSON. 4k is plenty.
        max_output_tokens=4096,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    initial_message = (
        "Phase: RESEARCH + START\n"
        "Your only task for this phase:\n"
        "1. Do at most 1-2 quick searches to fill gaps in the user request"
        "For example (a short weather summary, "
        "2-4 key neighborhoods, any travel advisories, optimal route covering all destinations).\n"
        "2. Emit the START event immediately after. Keep the start_details "
        "costs as rough estimates.\n"
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        "Begin now."
    )

    result = await run_chat_loop(
        initial_message=initial_message,
        config=config,
        node_name="research",
        next_event_number=state.get("next_event_number", 1),
        mode=state.get("mode", "autonomous"),
        prior_events=state.get("prior_events", []) or [],
        stop_after_start=True,
    )
    research_emitted = list(result.emitted_events or [])

    # Extract the START event (and its journey order) from this phase's
    # emissions so the day planners see it in prior_events and can be given an
    # explicit, mandatory destination order.
    existing_prior = list(state.get("prior_events", []) or [])
    start_event = next(
        (e for e in research_emitted if (e or {}).get("event_type") == "START"),
        None,
    )
    journey: list = []
    if start_event:
        journey = list(((start_event.get("start_details") or {}).get("journey") or []))
        # Avoid double-adding START on resume (it may already be persisted).
        if not any((e or {}).get("event_type") == "START" for e in existing_prior):
            existing_prior.append(start_event)

    if not result.success:
        # Even if the LLM phase failed, hand the baseline facts to the day
        # planner so planning can proceed with SOMETHING rather than nothing.
        log.warning("Research phase failed", error=result.error)
        return {
            "research_facts": {},
            "journey": journey,
            "prior_events": existing_prior,
            "next_event_number": 1,   # day 1 starts fresh from event 1
            "current_day": 1
        }

    llm_facts = await _parse_llm_research_json(result.last_text)
    research_facts = await _truncate_research_facts(llm_facts)

    log.info("Research phase complete", journey=journey)

    return {
        "research_facts": research_facts,
        "journey": journey,
        "prior_events": existing_prior,
        "next_event_number": 1,   # day 1 starts fresh from event 1
        "current_day": 1
    }
