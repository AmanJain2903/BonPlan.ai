"""
LangGraph graph definitions for BonPlan.

build_planner_graph() → compiled StateGraph for autonomous trip planning.
build_editor_graph()  → stub; returns None until editing mode is implemented.

Graph topology - Planning Mode (autonomous mode/collaborative mode):

  START
    │
    ▼
  bootstrap
    │
    ▼
  research_and_start
    │
    ▼
  collaboration_checkpoint  ← no-op today; future interrupt point (for human intervention in collaborative mode)
    │
    ▼ (routed by _should_plan_day)
  day_planner ──────────────────────┐
    │  (increments current_day)     │
    │  routed by _should_continue   │
    ▼ (more days)                   │
  day_planner (loop) ◄──────────────┘
    │ (no more days)
    ▼
  finalizer
    │
    ▼
   END
"""
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.nodes.bootstrap import bootstrap_node
from app.agent.langgraph_runtime.nodes.research import research_node
from app.agent.langgraph_runtime.nodes.collaboration_checkpoint import (
    collaboration_checkpoint_node,
)
from app.agent.langgraph_runtime.nodes.day_planner import day_planner_node
from app.agent.langgraph_runtime.nodes.finalizer import finalizer_node
from app.agent.core.runtime import runtime

from app.logging import get_agent_logger

log = get_agent_logger("graph")


def _route(state: PlannerState):
    # A cancelled/errored run is terminal — the frontend has already been told
    # to stop via the `error` chunk, so we MUST NOT run finalizer (which would
    # try to emit more events and confuse the client).
    if state.get("cancelled"):
        log.info(f"Cancelled state detected. Routing to END", state=state)
        return END
    current_day = state.get("current_day", 1)
    total_days = state.get("total_days", 1)
    return "day_planner" if current_day <= total_days else "finalizer"


def _route_after_bootstrap(state: PlannerState):
    if state.get("cancelled"):
        log.info(f"Cancelled state detected. Routing to END", state=state)
        return END
    # Resuming with at least one day already in progress → skip research +
    # START (START must not be re-emitted) and jump straight to day loop.
    if state.get("is_resuming") and state.get("current_day", 0) > 0:
        return "collaboration_checkpoint"
    return "research_and_start"


def build_planner_graph(checkpointer=None):
    """
    Build and compile the autonomous/collaborative planner graph.

    Parameters
    ----------
    checkpointer : optional
        A LangGraph checkpointer (e.g. AsyncPostgresSaver).
    """
    builder = StateGraph(PlannerState)

    builder.add_node("bootstrap", bootstrap_node)
    builder.add_node("research_and_start", research_node)
    builder.add_node("collaboration_checkpoint", collaboration_checkpoint_node)
    builder.add_node("day_planner", day_planner_node)
    builder.add_node("finalizer", finalizer_node)

    builder.add_edge(START, "bootstrap")
    builder.add_conditional_edges(
        "bootstrap",
        _route_after_bootstrap,
        {
            "research_and_start": "research_and_start",
            "collaboration_checkpoint": "collaboration_checkpoint",
            END: END,
        },
    )
    builder.add_edge("research_and_start", "collaboration_checkpoint")
    builder.add_conditional_edges(
        "collaboration_checkpoint",
        _route,
        {"day_planner": "day_planner", "finalizer": "finalizer", END: END},
    )
    builder.add_conditional_edges(
        "day_planner",
        _route,
        {"day_planner": "day_planner", "finalizer": "finalizer", END: END},
    )
    builder.add_edge("finalizer", END)

    _checkpointer = checkpointer or MemorySaver()
    return builder.compile(checkpointer=_checkpointer)


def build_editor_graph():
    """Stub — editing mode not implemented yet."""
    # TODO Implement editing graph.
    # The graph must NEVER emit a START event (it receives existing events and
    # only emits the modified ones identified by edit_scope).
    return None


# Module-level singleton for the default autonomous graph.
# Callers that need a custom checkpointer should call build_planner_graph() directly.
_default_graph = None


def get_planner_graph():
    # Prefer the runtime-compiled graph (built with the real checkpointer in
    # agent_runtime_context). Fall back to a lazily-built MemorySaver graph
    # for standalone callers / tests that don't go through the lifespan.
    try:
        if runtime.planner_graph is not None:
            log.info("Using runtime-compiled graph")
            return runtime.planner_graph
    except Exception:
        pass
    global _default_graph
    if _default_graph is None:
        _default_graph = build_planner_graph()
    log.info("Using default graph built with MemorySaver")
    return _default_graph
