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
from typing import Any, Dict, Optional

from google.genai import types

from app.logging import get_agent_logger, set_agent_log_context
from app.agent.core.runtime import runtime
from app.agent.langgraph_runtime.gemini_adapter import run_chat_loop
from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.streaming import emit
from app.agent.schemas.structuredInput import TripInput

log = get_agent_logger("research")

_AUTONOMOUS_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "prompts", "autonomousPlannerPrompt.md"
)
with open(_AUTONOMOUS_PROMPT_PATH, "r", encoding="utf-8") as _f:
    AUTONOMOUS_SYSTEM_PROMPT = _f.read()

# _COLLABORATIVE_PROMPT_PATH = os.path.join(
#     os.path.dirname(__file__), "..", "..", "prompts", "collaborativePlannerPrompt.md"
# )
# with open(_COLLABORATIVE_PROMPT_PATH, "r", encoding="utf-8") as _f:
#     COLLABORATIVE_SYSTEM_PROMPT = _f.read()

# _EDITING_PROMPT_PATH = os.path.join(
#     os.path.dirname(__file__), "..", "..", "prompts", "editingPlannerPrompt.md"
# )
# with open(_EDITING_PROMPT_PATH, "r", encoding="utf-8") as _f:
#     EDITING_SYSTEM_PROMPT = _f.read()

_RESEARCH_FACTS_SIZE_LIMIT = 2048  # bytes


async def _truncate_research_facts(facts: dict) -> dict:
    raw = json.dumps(facts, default=str)
    if len(raw.encode()) <= _RESEARCH_FACTS_SIZE_LIMIT:
        return facts
    # Trim in priority order — least useful keys dropped first.
    for key in ("notes", "web_snippets", "weather_detail", "extra", "neighborhoods"):
        facts.pop(key, None)
        if len(json.dumps(facts, default=str).encode()) <= _RESEARCH_FACTS_SIZE_LIMIT:
            return facts
    # Still too big — clip string fields.
    for k, v in list(facts.items()):
        if isinstance(v, str) and len(v) > 200:
            facts[k] = v[:200] + "…"
    raw = json.dumps(facts, default=str)
    if len(raw.encode()) <= _RESEARCH_FACTS_SIZE_LIMIT:
        return facts
    return {"schema_version": 1, "note": "research_facts truncated"}


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
        return {}


async def _deterministic_facts(trip_data: TripInput) -> dict:
    """
    Build a compact, trip-length-independent facts dict directly from the
    user input — no LLM or MCP call required. This is always present so the
    day planner has baseline context even if the LLM research JSON fails.
    """
    dests = [
        {
            "city": d.city or "",
            "state": d.state or "",
            "country": d.country or "",
            "lat": round(d.lat, 4),
            "lng": round(d.lng, 4),
        }
        for d in (trip_data.destinations or [])
    ]
    origin = trip_data.origin
    return {
        "schema_version": 1,
        "origin": {
            "city": origin.city or "",
            "country": origin.country or "",
            "lat": round(origin.lat, 4),
            "lng": round(origin.lng, 4),
            "timezone": trip_data.start_date.timezoneId,
        },
        "destinations": dests,
        "dates": {
            "start_local": trip_data.start_date.localTimeString,
            "start_utc": trip_data.start_date.utcTimeString,
            "end_local": trip_data.end_date.localTimeString,
            "end_utc": trip_data.end_date.utcTimeString,
            "origin_timezone": trip_data.start_date.timezoneId,
            "destination_timezone": trip_data.end_date.timezoneId,
        },
        "travelers": {
            "adults": trip_data.adults,
            "children": trip_data.children,
        },
        "pace": trip_data.pace,
        "budget": trip_data.budget,
    }


async def research_node(state: PlannerState) -> Dict[str, Any]:
    trip_id = state.get("trip_id") or "unknown"
    set_agent_log_context(run_id=trip_id, node="research", day=0)

    trip_payload = state.get("trip_input", {})
    trip_data = TripInput(**trip_payload)

    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=False
        ),
        tools=[runtime.research_tool_block or runtime.planner_tool_block],
        system_instruction=AUTONOMOUS_SYSTEM_PROMPT,
        temperature=0.6,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    base_facts = await _deterministic_facts(trip_data)

    initial_message = (
        f"User Request:\n{trip_data.model_dump_json()}\n\n"
        f"Baseline Facts (already known — do NOT re-fetch):\n"
        f"{json.dumps(base_facts, default=str)}\n\n"
        "Phase: RESEARCH + START\n"
        "Your only task for this phase:\n"
        "1. Do at most 1-2 quick searches to fill gaps in the baseline facts "
        "(a short weather summary, "
        "2-4 key neighborhoods, any travel advisories, optimal route covering all destinations).\n"
        "2. Emit the START event immediately after. Keep the start_details "
        "costs as rough estimates.\n"
        "3. After emitting START, output EXACTLY ONE JSON object (no prose, "
        "no markdown fences) with these keys:\n"
        "   - Timezones: timezone information for origin and destinations"
        "   - weather_summary: one sentence about expected weather\n"
        "   - neighborhoods: list of 2-4 short neighborhood names\n"
        "   - notes: <=200 chars of travel-relevant notes (advisories, events, "
        "peak-season flags)\n"
        "Then STOP. Do not emit anything else.\n"
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
    accumulated_prior = list(state.get("prior_events", []) or []) + research_emitted

    if not result.success:
        # Even if the LLM phase failed, hand the baseline facts to the day
        # planner so planning can proceed with SOMETHING rather than nothing.
        log.warning("Research phase failed. Handling just the baseline facts", error=result.error)
        return {
            "research_facts": await _truncate_research_facts(base_facts),
            "phase": "done",
            "cancelled": True,
            "next_event_number": result.next_event_number,
            "prior_events": accumulated_prior,
        }

    # Merge LLM-supplied research into the deterministic baseline. Baseline
    # wins on any key collision so the model can't fabricate trip metadata.
    llm_facts = await _parse_llm_research_json(result.last_text)
    merged = {**llm_facts, **base_facts}
    research_facts = await _truncate_research_facts(merged)

    log.info(
        "Research phase complete",
        next_event_number=result.next_event_number,
        llm_fact_keys=list(llm_facts.keys()),
        facts_bytes=len(json.dumps(research_facts, default=str).encode()),
    )

    return {
        "research_facts": research_facts,
        "next_event_number": 1,   # day 1 starts fresh from event 1
        "current_day": 1,
        "phase": "day",
        "prior_events": accumulated_prior,
    }
