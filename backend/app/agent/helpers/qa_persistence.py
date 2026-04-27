"""
Helpers for persisting and loading collaborative Q&A pairs.

Persistence is fire-and-forget from the hot path (gemini_adapter / nodes).
Loading is awaited in the SSE endpoint before the generator starts.
"""
import asyncio

from sqlalchemy import select

from app.database.database import Session
from app.database.models.tripCollabQATable import TripCollabQA
from app.logging import get_agent_logger

log = get_agent_logger("qa_persistence")


async def persist_qa_entry(trip_id: str, user_id: str, qa_entry: dict) -> None:
    """
    Upsert one Q&A entry into trip_collab_qa for (trip_id, user_id).

    Seed entries (context == "seed") replace any existing seed so a fresh run
    that re-asks overwrites the stale answer.  Day entries are always appended.
    """
    try:
        async with Session() as db:
            row = (
                await db.execute(
                    select(TripCollabQA).where(
                        TripCollabQA.trip_id == trip_id,
                        TripCollabQA.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()

            if row is None:
                row = TripCollabQA(
                    trip_id=trip_id,
                    user_id=user_id,
                    qa_pairs=[qa_entry],
                )
                db.add(row)
            else:
                pairs = list(row.qa_pairs or [])
                if qa_entry.get("context") == "seed":
                    pairs = [p for p in pairs if p.get("context") != "seed"]
                pairs.append(qa_entry)
                row.qa_pairs = pairs

            await db.commit()
    except Exception as exc:
        log.warning("Failed to persist Q&A entry. This was after a successful fire-and-forget task scheduled.", trip_id=trip_id, user_id=user_id, error=str(exc))


def fire_persist_qa(trip_id: str, user_id: str, qa_entry: dict) -> None:
    """Schedule persist_qa_entry as a background task (non-blocking)."""
    try:
        asyncio.create_task(persist_qa_entry(trip_id, user_id, qa_entry))
    except Exception as exc:
        log.warning("Failed to schedule Q&A persist task", trip_id=trip_id, user_id=user_id, error=str(exc))


async def load_collab_qa(trip_id: str, user_id: str) -> list:
    """
    Return all persisted Q&A pairs for (trip_id, user_id), or [].

    Callers use the full list to:
      - Extract the seed answer (context == "seed")
      - Inject all non-seed pairs into day-planner prompts so the LLM doesn't
        repeat questions across resume sessions.
    """
    try:
        async with Session() as db:
            row = (
                await db.execute(
                    select(TripCollabQA).where(
                        TripCollabQA.trip_id == trip_id,
                        TripCollabQA.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()

            return list(row.qa_pairs or []) if row else []
    except Exception as exc:
        log.warning("Failed to load collab Q&A", trip_id=trip_id, error=str(exc))
        return []
