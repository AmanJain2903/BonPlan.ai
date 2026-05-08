"""Snapshot, status, and atomic commit helpers for itinerary edits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.helpers.itinerary_event_cost import sum_chargeable_cost_usd
from app.database.models.tripItinerariesTable import TripItinerary, TripItineraryStatus
from app.database.models.tripItinerarySnapshotsTable import TripItinerarySnapshot
from app.database.models.tripsTable import PlanStatus, Trip

from .event_utils import (
    canonicalize_events,
    ensure_event_identities,
    events_hash,
)


class EditConflictError(RuntimeError):
    """Raised when the edit was based on a stale itinerary."""


class EditStatusError(RuntimeError):
    """Raised when a trip cannot enter/leave editing status."""


@dataclass
class CommitResult:
    events: list[dict[str, Any]]
    snapshot_cursor: int
    events_hash: str
    cost: float
    title: Optional[str]
    tips: list[str]


def _patch_end_cost(events: list[dict[str, Any]], cost: float) -> list[dict[str, Any]]:
    result = canonicalize_events(events)
    for idx, event in enumerate(result):
        if event.get("event_type") != "END":
            continue
        end_details = dict(event.get("end_details") or {})
        end_details["trip_cost"] = cost
        result[idx] = {**event, "end_details": end_details}
        break
    return result


async def start_edit_status(db: AsyncSession, trip_id: str) -> None:
    """Flip Trip.status GENERATED -> EDITING for a real editing pipeline run."""
    trip = (
        await db.execute(
            select(Trip)
            .where(Trip.id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if trip is None:
        raise EditStatusError("Trip not found.")
    current_status = trip.status.value if hasattr(trip.status, "value") else str(trip.status)
    if current_status == PlanStatus.EDITING.value:
        raise EditStatusError("This itinerary is already being edited. Please retry after the current edit finishes.")
    if current_status != PlanStatus.GENERATED.value:
        raise EditStatusError("Only generated itineraries can be edited.")
    trip.status = PlanStatus.EDITING
    await db.commit()


async def restore_generated_status(db: AsyncSession, trip_id: str) -> None:
    """Best-effort cleanup: Trip.status EDITING -> GENERATED; itinerary stays generated."""
    trip = (
        await db.execute(
            select(Trip)
            .where(Trip.id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if trip is None:
        return
    current_status = trip.status.value if hasattr(trip.status, "value") else str(trip.status)
    if current_status == PlanStatus.EDITING.value:
        trip.status = PlanStatus.GENERATED
    itinerary = (
        await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if itinerary is not None:
        itinerary.status = TripItineraryStatus.GENERATED
    await db.commit()


async def ensure_initial_snapshot(
    db: AsyncSession,
    *,
    trip_id: str,
    itinerary: TripItinerary,
    prepared_events: list[dict[str, Any]],
) -> None:
    existing = (
        await db.execute(
            select(TripItinerarySnapshot)
            .where(
                TripItinerarySnapshot.trip_id == trip_id,
                TripItinerarySnapshot.version_index == 0,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    db.add(
        TripItinerarySnapshot(
            trip_id=trip_id,
            version_index=0,
            events=canonicalize_events(prepared_events),
            cost=itinerary.cost,
            title=itinerary.title,
            tips=list(itinerary.tips or []),
            description="Original generated itinerary.",
        )
    )
    await db.flush()


async def commit_candidate(
    db: AsyncSession,
    *,
    trip_id: str,
    candidate_events: list[dict[str, Any]],
    base_snapshot_cursor: Optional[int],
    base_events_hash: Optional[str],
    description: str,
) -> CommitResult:
    """Atomically write one fully validated candidate and append a snapshot."""
    trip = (
        await db.execute(
            select(Trip)
            .where(Trip.id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    itinerary = (
        await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if trip is None or itinerary is None:
        raise EditConflictError("Trip or itinerary not found.")

    trip_status = trip.status.value if hasattr(trip.status, "value") else str(trip.status)
    if trip_status not in {PlanStatus.EDITING.value, PlanStatus.GENERATED.value}:
        raise EditConflictError("Only generated itineraries can be edited.")

    itinerary_status = itinerary.status.value if hasattr(itinerary.status, "value") else str(itinerary.status)
    if itinerary_status != TripItineraryStatus.GENERATED.value:
        raise EditConflictError("Itinerary row is not in generated state.")

    current_events, _ = ensure_event_identities(itinerary.events or [])
    current_cursor = int(itinerary.snapshot_cursor or 0)
    current_hash = events_hash(current_events)

    if base_snapshot_cursor is not None and int(base_snapshot_cursor) != current_cursor:
        raise EditConflictError(
            f"Itinerary changed since this edit started (cursor {current_cursor}, expected {base_snapshot_cursor})."
        )
    if base_events_hash and base_events_hash != current_hash:
        raise EditConflictError("Itinerary changed since this edit started. Reload and try again.")

    await ensure_initial_snapshot(
        db,
        trip_id=trip_id,
        itinerary=itinerary,
        prepared_events=current_events,
    )

    await db.execute(
        delete(TripItinerarySnapshot).where(
            TripItinerarySnapshot.trip_id == trip_id,
            TripItinerarySnapshot.version_index > current_cursor,
        )
    )

    next_cursor = current_cursor + 1
    normalized_candidate, _ = ensure_event_identities(candidate_events)
    cost = sum_chargeable_cost_usd(normalized_candidate)
    normalized_candidate = _patch_end_cost(normalized_candidate, cost)

    db.add(
        TripItinerarySnapshot(
            trip_id=trip_id,
            version_index=next_cursor,
            events=canonicalize_events(normalized_candidate),
            cost=cost,
            title=itinerary.title,
            tips=list(itinerary.tips or []),
            description=description[:1000],
        )
    )

    itinerary.events = canonicalize_events(normalized_candidate)
    itinerary.cost = cost
    itinerary.snapshot_cursor = next_cursor
    itinerary.status = TripItineraryStatus.GENERATED
    trip.status = PlanStatus.GENERATED
    await db.commit()

    events_for_response = canonicalize_events(normalized_candidate, include_display_numbers=True)
    return CommitResult(
        events=events_for_response,
        snapshot_cursor=next_cursor,
        events_hash=events_hash(normalized_candidate),
        cost=cost,
        title=itinerary.title,
        tips=list(itinerary.tips or []),
    )


async def list_snapshots(db: AsyncSession, *, trip_id: str) -> list[dict[str, Any]]:
    snapshots = (
        await db.execute(
            select(TripItinerarySnapshot)
            .where(TripItinerarySnapshot.trip_id == trip_id)
            .order_by(TripItinerarySnapshot.version_index.asc())
        )
    ).scalars().all()
    return [
        {
            "id": str(snapshot.id),
            "trip_id": str(snapshot.trip_id),
            "version_index": snapshot.version_index,
            "events_count": len(snapshot.events or []),
            "cost": snapshot.cost,
            "title": snapshot.title,
            "description": snapshot.description,
            "created_at": snapshot.created_at,
        }
        for snapshot in snapshots
    ]


async def revert_to_snapshot(
    db: AsyncSession,
    *,
    trip_id: str,
    version_index: int,
) -> CommitResult:
    """Restore an existing clean snapshot and move the cursor without new history."""
    trip = (
        await db.execute(
            select(Trip)
            .where(Trip.id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    itinerary = (
        await db.execute(
            select(TripItinerary)
            .where(TripItinerary.trip_id == trip_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    snapshot = (
        await db.execute(
            select(TripItinerarySnapshot)
            .where(
                TripItinerarySnapshot.trip_id == trip_id,
                TripItinerarySnapshot.version_index == version_index,
            )
        )
    ).scalar_one_or_none()

    if trip is None or itinerary is None:
        raise EditConflictError("Trip or itinerary not found.")
    if snapshot is None:
        raise EditConflictError(f"Snapshot version {version_index} was not found.")
    trip_status = trip.status.value if hasattr(trip.status, "value") else str(trip.status)
    if trip_status != PlanStatus.GENERATED.value:
        raise EditConflictError("Only generated itineraries can be reverted.")
    itinerary_status = itinerary.status.value if hasattr(itinerary.status, "value") else str(itinerary.status)
    if itinerary_status != TripItineraryStatus.GENERATED.value:
        raise EditConflictError("Only generated itineraries can be reverted.")

    trip.status = PlanStatus.EDITING
    await db.flush()

    prepared_events, _ = ensure_event_identities(snapshot.events or [])
    cost = snapshot.cost
    if cost is None:
        cost = sum_chargeable_cost_usd(prepared_events)
    prepared_events = _patch_end_cost(prepared_events, float(cost))

    itinerary.events = canonicalize_events(prepared_events)
    itinerary.cost = float(cost)
    itinerary.title = snapshot.title
    itinerary.tips = list(snapshot.tips or [])
    itinerary.snapshot_cursor = int(version_index)
    itinerary.status = TripItineraryStatus.GENERATED
    trip.status = PlanStatus.GENERATED
    await db.commit()

    return CommitResult(
        events=canonicalize_events(prepared_events, include_display_numbers=True),
        snapshot_cursor=int(version_index),
        events_hash=events_hash(prepared_events),
        cost=float(cost),
        title=itinerary.title,
        tips=list(itinerary.tips or []),
    )
