"""
LangGraph graph definitions for BonPlan.

build_planner_graph() → compiled StateGraph for autonomous trip planning.
build_editor_graph()  → compiled StateGraph for itinerary chat.

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
  collaboration_checkpoint  ← no-op in autonomous; in collaborative, runs a
    │                         small LLM call to generate ONE seed question
    │                         tailored to the actual trip + research facts,
    │                         then awaits the user's reply before day planning.
    ▼ (routed by _route_initial)
  day_planner
    │  (always routes to day_validator)
    ▼
  day_validator  ──────────────────────────────────────────────┐
    │  (on error, attempts < MAX: same current_day)            │
    │  (on success / max attempts: current_day += 1)           │
    ├─ errors + attempts ≤ MAX ──────────────────────────────► day_planner (retry same day)
    │
    ├─ no errors, current_day ≤ total_days ─────────────────► day_planner (next day)
    │
    └─ no errors, current_day > total_days
         │
         ▼
  open_booking_guard ───────────────┐ (close_pass=True → re-run last day via day_planner)
    │                               │
    ▼ (no open bookings)            ▼
  finalizer                     day_planner → day_validator (close pass)
    │
    ▼
   END
"""
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.agent.langgraph_runtime.state import PlannerState
from app.agent.langgraph_runtime.nodes.bootstrap import bootstrap_node
from app.agent.langgraph_runtime.nodes.research import research_node
from app.agent.langgraph_runtime.nodes.collaboration_checkpoint import (
    collaboration_checkpoint_node,
)
from app.agent.langgraph_runtime.nodes.day_planner import day_planner_node
from app.agent.langgraph_runtime.nodes.day_validator import day_validator_node, MAX_VALIDATION_ATTEMPTS
from app.agent.langgraph_runtime.nodes.open_booking_guard import open_booking_guard_node
from app.agent.langgraph_runtime.nodes.finalizer import finalizer_node
from app.agent.core.runtime import runtime

from app.logging import get_agent_logger

log = get_agent_logger("graph")


def _route_after_bootstrap(state: PlannerState):
    if state.get("cancelled"):
        log.info("Cancelled state detected. Routing to END")
        return END
    # Resuming with at least one day already in progress → skip research +
    # START (START must not be re-emitted) and jump straight to checkpoint
    # then day loop.
    if state.get("is_resuming") and state.get("current_day", 0) > 0:
        return "collaboration_checkpoint"
    return "research_and_start"


def _route_initial(state: PlannerState):
    """Route from collaboration_checkpoint or resume to first day / guard."""
    if state.get("cancelled"):
        log.info("Cancelled state detected. Routing to END")
        return END
    current_day = state.get("current_day", 1)
    total_days = state.get("total_days", 1)
    return "day_planner" if current_day <= total_days else "open_booking_guard"


def _route_after_day_planner(state: PlannerState):
    """After day_planner: go to day_validator, or loop back on turn-cap retry."""
    if state.get("cancelled"):
        log.info("Cancelled state detected. Routing to END")
        return END
    if state.get("turn_cap_retry"):
        log.info("Turn cap retry — routing back to day_planner", day=state.get("current_day"))
        return "day_planner"
    return "day_validator"


def _route_after_validator(state: PlannerState):
    """
    After day_validator:
      - errors + attempts within limit → day_planner (retry same day)
      - otherwise (success or max exceeded):
          current_day ≤ total_days → day_planner (next day)
          current_day > total_days → open_booking_guard
    """
    if state.get("cancelled"):
        log.info("Cancelled state detected. Routing to END")
        return END
    errors = state.get("day_validation_errors")
    attempts = state.get("day_validator_attempts", 0)
    if errors and attempts <= MAX_VALIDATION_ATTEMPTS:
        return "day_planner"
    current_day = state.get("current_day", 1)
    total_days = state.get("total_days", 1)
    return "day_planner" if current_day <= total_days else "open_booking_guard"


def _route_after_guard(state: PlannerState):
    if state.get("cancelled"):
        log.info("Cancelled state detected. Routing to END")
        return END
    # Guard sets close_pass=True when it needs the day_planner to run one
    # more close-only pass on the final day.
    return "day_planner" if state.get("close_pass") else "finalizer"


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
    builder.add_node("day_validator", day_validator_node)
    builder.add_node("open_booking_guard", open_booking_guard_node)
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
        _route_initial,
        {
            "day_planner": "day_planner",
            "open_booking_guard": "open_booking_guard",
            END: END,
        },
    )
    # day_planner → day_validator, or loops back to itself on turn-cap retry
    builder.add_conditional_edges(
        "day_planner",
        _route_after_day_planner,
        {"day_validator": "day_validator", "day_planner": "day_planner", END: END},
    )
    # day_validator decides: retry same day, advance to next day, or guard
    builder.add_conditional_edges(
        "day_validator",
        _route_after_validator,
        {
            "day_planner": "day_planner",
            "open_booking_guard": "open_booking_guard",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "open_booking_guard",
        _route_after_guard,
        {"day_planner": "day_planner", "finalizer": "finalizer", END: END},
    )
    builder.add_edge("finalizer", END)

    _checkpointer = checkpointer or MemorySaver()
    return builder.compile(checkpointer=_checkpointer)


def build_editor_graph(checkpointer=None):
    from app.agent.langgraph_runtime.editor_graph import build_editor_graph as _build
    return _build(checkpointer=checkpointer)


# Module-level singleton for the default autonomous graph.
# Callers that need a custom checkpointer should call build_planner_graph() directly.
_default_graph = None
_default_editor_graph = None


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


def get_editor_graph():
    try:
        if runtime.editor_graph is not None:
            log.info("Using runtime-compiled editor graph")
            return runtime.editor_graph
    except Exception:
        pass

    global _default_editor_graph
    if _default_editor_graph is None:
        _default_editor_graph = build_editor_graph()
    log.info("Using default editor graph built with MemorySaver")
    return _default_editor_graph
