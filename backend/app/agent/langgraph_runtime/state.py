"""
PlannerState — the single shared TypedDict for the BonPlan LangGraph planner.

Fields that carry a reducer annotation (operator.add) are append-only so that
concurrent / looping nodes never overwrite each other's events.

Fields marked 'Reserved' are typed now but unused until the collaborative /
editing modes are implemented.  They are always None in autonomous mode.
"""

from operator import add
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict


class PlannerState(TypedDict, total=False):
    # ── Core trip data ────────────────────────────────────────────────────────
    trip_input: dict                        # serialized TripInput payload
    mode: Literal["autonomous", "collaborative", "editing"]

    # ── Progress tracking ─────────────────────────────────────────────────────
    current_day: int                        # 1-based; 0 before any day runs
    total_days: int
    next_event_number: int                  # per-day counter (resets to 1 each day)
    is_complete: bool                       # True after END event is emitted
    phase: Literal["bootstrap", "research", "collaboration", "day", "finalize", "done"]

    # ── Resume ────────────────────────────────────────────────────────────────
    is_resuming: bool                       # True if picking up prior events
    prior_events: list                      # validated events already persisted

    # ── Research artefacts ────────────────────────────────────────────────────
    research_facts: dict                    # compact JSON ≤ 2 KB; schema_version: 1

    # ── Journey order (locked in by research/START) ───────────────────────────
    # Extracted from the START event's `start_details.journey` and surfaced
    # explicitly to every day_planner invocation so they cannot drift from the
    # destination order committed by the research phase.
    journey: list                           # ordered list of destination names

    # ── Identity  ─────────────────────────────
    owner_id: Optional[str]
    trip_id: Optional[str]

    # ── Cancellation ──────────────────────────────────────────────────────────
    cancelled: bool

    # ── Open-booking guard ────────────────────────────────────────────────────
    # Set by the open_booking_guard node when it detects un-closed bookings
    # (HOTEL_CHECKIN without HOTEL_CHECKOUT, etc.) and routes back to the
    # day planner for a dedicated close-only pass on the final day.
    close_pass: bool                        # True → day_planner runs in close-only mode
    close_pass_attempted: bool              # True after one close pass has run; prevents infinite loops



    

    # ── Reserved: collaborative mode ──────────────────────────────────────────
    pending_human_request: Optional[str]    # question to surface to the user
    human_response: Optional[str]           # user's answer

    # ── Reserved: editing mode ────────────────────────────────────────────────
    edit_scope: Optional[list]              # list of (day_number, event_number) pairs
