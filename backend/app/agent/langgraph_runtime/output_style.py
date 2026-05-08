"""User-facing wording helpers for streamed agent output."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Iterable

from app.agent.llm import litellm_types as types


_POLICY_HEADER = "# User-Facing Output Policy"

USER_FACING_OUTPUT_POLICY = """For any text that may be shown to users, including progress text, questions, summaries, clarification messages, and rejection messages:
- Write like a travel product, not like an implementation log.
- Talk about the trip, itinerary, days, stops, places, routes, bookings, and choices.
- Do not expose implementation terms such as tool names, function calls, event_type, START/END events, schema, JSON, MCP, graph, node, runtime, emit, emitted, or emitting.
- If you need to describe internal work, translate it into product language: "checking routes", "adding the next stop", "updating the itinerary", or "wrapping up the trip".

Structured tool arguments and strict JSON fields may still use the required schema names."""


def with_user_facing_output_policy(
    config: types.GenerateContentConfig,
) -> types.GenerateContentConfig:
    """Return a config whose system prompt includes the shared output policy."""
    instruction = (config.system_instruction or "").strip()
    if _POLICY_HEADER in instruction:
        return config
    next_instruction = (
        f"{instruction}\n\n{_POLICY_HEADER}\n\n{USER_FACING_OUTPUT_POLICY}"
        if instruction
        else f"{_POLICY_HEADER}\n\n{USER_FACING_OUTPUT_POLICY}"
    )
    return replace(config, system_instruction=next_instruction)
