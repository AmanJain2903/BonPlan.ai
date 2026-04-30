"""LangGraph assembly for itinerary chat."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.nodes.conversational import conversational_node
from app.agent.langgraph_runtime.nodes.editor_bootstrap import editor_bootstrap_node
from app.agent.langgraph_runtime.nodes.intent_classifier import intent_classifier_node
from app.agent.langgraph_runtime.nodes.structural_classifier import structural_classifier_node


def _route_after_intent(state: EditorState):
    if state.get("cancelled"):
        return END
    return "editor_bootstrap" if state.get("needs_itinerary_context") else "conversational"


def _route_after_bootstrap(state: EditorState):
    if state.get("cancelled"):
        return END
    return "structural_classifier"


def _route_after_structural(state: EditorState):
    if state.get("cancelled"):
        return END
    return "conversational"


def build_editor_graph(checkpointer=None):
    builder = StateGraph(EditorState)

    builder.add_node("intent_classifier", intent_classifier_node)
    builder.add_node("editor_bootstrap", editor_bootstrap_node)
    builder.add_node("structural_classifier", structural_classifier_node)
    builder.add_node("conversational", conversational_node)

    builder.add_edge(START, "intent_classifier")
    builder.add_conditional_edges(
        "intent_classifier",
        _route_after_intent,
        {
            "editor_bootstrap": "editor_bootstrap",
            "conversational": "conversational",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "editor_bootstrap",
        _route_after_bootstrap,
        {
            "structural_classifier": "structural_classifier",
            END: END,
        },
    )
    builder.add_conditional_edges(
        "structural_classifier",
        _route_after_structural,
        {
            "conversational": "conversational",
            END: END,
        },
    )
    builder.add_edge("conversational", END)

    _checkpointer = checkpointer or MemorySaver()
    return builder.compile(checkpointer=_checkpointer)
