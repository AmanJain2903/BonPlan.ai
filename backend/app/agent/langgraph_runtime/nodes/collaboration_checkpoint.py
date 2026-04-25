"""
Collaboration checkpoint node — no-op in autonomous mode.

This node exists as an architectural hook for future collaborative mode.
When collaborative mode is implemented, this node will call `interrupt()` with
`state["pending_human_request"]` and wait for `state["human_response"]`.

Today it is a pure pass-through.
"""
from typing import Any, Dict

from app.agent.langgraph_runtime.state import PlannerState

from app.logging import get_agent_logger

logger = get_agent_logger("nodes.collaboration_checkpoint")


async def collaboration_checkpoint_node(state: PlannerState) -> Dict[str, Any]:
    # TODO (collaborative mode): check state["mode"] == "collaborative" and
    # call interrupt(state["pending_human_request"]) here.
    return {}
