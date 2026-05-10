"""EditorState — shared TypedDict for itinerary chat graph."""

from typing import Literal
from typing_extensions import TypedDict


class EditorState(TypedDict, total=False):
    # ── Identity ──────────────────────────────────────────────────────────────
    user_id: str
    trip_id: str

    # ── Input (per message) ───────────────────────────────────────────────────
    user_message: str
    attached_events: list
    chat_history: list

    # ── Session cache (optional; supplied by caller/test harness) ─────────────
    cached_itinerary_events: list
    cached_trip_input: dict
    cached_research_facts: dict
    force_reload_itinerary: bool

    # ── Context loaded at bootstrap ───────────────────────────────────────────
    current_itinerary_events: list
    trip_input: dict
    research_facts: dict
    smart_anchors: list
    snapshot_cursor: int
    base_events_hash: str
    client_base_snapshot_cursor: int
    client_base_events_hash: str
    itinerary_context_loaded_from_cache: bool

    # ── Classification ────────────────────────────────────────────────────────
    intent: Literal["conversation", "edit"]
    needs_itinerary_context: bool
    is_structural_change: bool
    structural_reason: str

    # ── Conversation ──────────────────────────────────────────────────────────
    conversation_notes: str

    # ── Model selection ───────────────────────────────────────────────────────
    use_fast_model: bool                    # True → use FAST_EDITOR_AGENT_MODEL

    # ── Control ───────────────────────────────────────────────────────────────
    cancelled: bool
