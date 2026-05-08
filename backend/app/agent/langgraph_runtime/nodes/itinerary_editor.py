"""LangGraph node that applies non-structural itinerary edits."""

from __future__ import annotations

from typing import Any, Dict

from app.agent.langgraph_runtime.editor_state import EditorState
from app.agent.langgraph_runtime.editing.engine import run_edit_engine
from app.agent.langgraph_runtime.streaming import emit
from app.database.database import Session
from app.logging import get_agent_logger

from app.agent.langgraph_runtime.editing.snapshot_service import (
    EditStatusError,
    restore_generated_status,
    start_edit_status,
)


log = get_agent_logger("itinerary_editor_node")


async def itinerary_editor_node(state: EditorState) -> Dict[str, Any]:
    trip_id = state.get("trip_id")
    if not trip_id:
        emit({"type": "error", "content": "Missing trip_id."})
        return {"cancelled": True}

    status_started = False
    try:
        async with Session() as db:
            await start_edit_status(db, str(trip_id))
        status_started = True
        emit({"type": "edit_status", "status": "started", "trip_status": "editing"})

        outcome = await run_edit_engine(state)

        if outcome.status == "committed" and outcome.commit:
            commit = outcome.commit
            emit({
                "type": "itinerary_replace",
                "events": commit.events,
                "snapshot_cursor": commit.snapshot_cursor,
                "events_hash": commit.events_hash,
                "cost": commit.cost,
                "title": commit.title,
                "tips": commit.tips,
            })
            emit({
                "type": "edit_commit",
                "snapshot_cursor": commit.snapshot_cursor,
                "events_hash": commit.events_hash,
                "summary": outcome.summary,
            })
            emit({"type": "summary", "content": outcome.summary})
            emit({"type": "edit_end", "status": "committed"})
            return {
                "current_itinerary_events": commit.events,
                "snapshot_cursor": commit.snapshot_cursor,
                "base_events_hash": commit.events_hash,
            }

        if outcome.status == "clarify":
            question = outcome.question or "Can you clarify that edit?"
            emit({"type": "edit_clarification", "question": question})
            emit({"type": "summary", "content": question})
            emit({"type": "edit_end", "status": "clarify"})
            return {}

        if outcome.status == "conflict":
            emit({
                "type": "edit_rejected",
                "reason": outcome.reason,
                "conflict": True,
            })
            emit({"type": "summary", "content": outcome.reason})
            emit({"type": "edit_end", "status": "conflict"})
            return {}

        if outcome.status == "rejected":
            payload: dict[str, Any] = {"type": "edit_rejected", "reason": outcome.reason}
            if outcome.validation_errors:
                payload["validation_errors"] = outcome.validation_errors
            emit(payload)
            message = outcome.reason
            if outcome.validation_errors:
                message = f"{message}\n\n" + "\n".join(f"- {err}" for err in outcome.validation_errors[:5])
            emit({"type": "summary", "content": message})
            emit({"type": "edit_end", "status": "rejected"})
            return {}

        emit({"type": "error", "content": outcome.reason or "Editing failed."})
        emit({"type": "edit_end", "status": "failed"})
        return {"cancelled": True}

    except EditStatusError as exc:
        emit({"type": "edit_rejected", "reason": str(exc)})
        emit({"type": "summary", "content": str(exc)})
        emit({"type": "edit_end", "status": "rejected"})
        return {}
    except Exception as exc:
        log.exception("Unhandled itinerary editor node error", error=str(exc))
        emit({"type": "error", "content": f"Editing failed: {exc}"})
        emit({"type": "edit_end", "status": "failed"})
        return {"cancelled": True}
    finally:
        if status_started:
            try:
                async with Session() as db:
                    await restore_generated_status(db, str(trip_id))
                emit({"type": "edit_status", "status": "finished", "trip_status": "generated"})
            except Exception as exc:
                log.exception("Failed to restore generated status after edit", error=str(exc))

