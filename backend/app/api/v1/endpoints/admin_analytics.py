# backend/app/api/v1/endpoints/admin_analytics.py

"""
Admin analytics endpoint for production dashboard rollups.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import cast, or_, select, String

from app.core.config import settings
from app.database.database import Session
from app.database.models.apiCacheTable import ApiCache
from app.database.models.placePhotoCache import PlacePhotoCache
from app.database.models.emailSubscriptionsTable import EmailSubscription
from app.database.models.rateLimitUsage import RateLimitUsage
from app.database.models.supportTicketsTable import SupportTicket, TicketStatus
from app.database.models.tripItinerariesTable import TripItinerary, TripItineraryStatus
from app.database.models.tripMembersTable import TripInvitationStatus, TripMember
from app.database.models.tripsTable import PlanningType, PlanStatus, Trip
from app.database.models.usersTable import User
from app.logging import get_api_logger

logger = get_api_logger("api.admin_analytics")
router = APIRouter()


async def _verify_admin(token: str) -> None:
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin privileges required.")


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value or "")


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _date_key(value: datetime | None) -> str | None:
    if not value:
        return None
    return value.date().isoformat()


def _sort_timestamp(value: datetime | None) -> float:
    if not value:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _pct(part: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round((part / total) * 100, 1)


def _avg(values: list[int | float]) -> float:
    values = [v for v in values if v is not None]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 1)


def _trip_days(trip: Trip, itinerary: TripItinerary | None) -> int | None:
    if itinerary and itinerary.days:
        return int(itinerary.days)
    try:
        start_ts = int((trip.start_date or {}).get("utcTimestamp", 0))
        end_ts = int((trip.end_date or {}).get("utcTimestamp", 0))
        if start_ts and end_ts:
            return max(1, int((end_ts - start_ts) / 86400) + 1)
    except Exception:
        return None
    return None


def _city_name(value: Any) -> str | None:
    if isinstance(value, dict):
        city = value.get("city") or value.get("name") or value.get("description")
        return str(city).strip() if city else None
    if isinstance(value, str):
        return value.strip() or None
    return None


def _build_empty_series(start: datetime | None, now: datetime) -> dict[str, dict[str, int]]:
    if not start:
        return {}
    days = max(1, min(366, (now.date() - start.date()).days + 1))
    return {
        (start.date() + timedelta(days=i)).isoformat(): {
            "date": (start.date() + timedelta(days=i)).isoformat(),
            "users": 0,
            "drafts": 0,
            "trips": 0,
            "generated": 0,
        }
        for i in range(days)
    }


@router.get("/overview", response_model=dict)
async def analytics_overview(
    token: str,
    days: int = Query(30, ge=0, le=3650),
    planning_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    auth_provider: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    await _verify_admin(token)

    now = datetime.now(timezone.utc)
    start = None if days == 0 else now - timedelta(days=days - 1)
    normalized_search = (search or "").strip().lower()

    async with Session() as db:
        try:
            user_stmt = select(User)
            if start:
                user_stmt = user_stmt.where(User.created_at >= start)
            if auth_provider and auth_provider != "all":
                user_stmt = user_stmt.where(User.auth_provider == auth_provider)
            if normalized_search:
                pattern = f"%{normalized_search}%"
                user_stmt = user_stmt.where(or_(
                    User.email.ilike(pattern),
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                ))
            users = (await db.execute(user_stmt)).scalars().all()

            trip_stmt = select(Trip)
            if start:
                trip_stmt = trip_stmt.where(Trip.created_at >= start)
            if planning_type and planning_type != "all":
                try:
                    trip_stmt = trip_stmt.where(Trip.planning_type == PlanningType(planning_type))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid planning_type filter.")
            if status and status != "all":
                try:
                    trip_stmt = trip_stmt.where(Trip.status == PlanStatus(status))
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid status filter.")
            if normalized_search:
                pattern = f"%{normalized_search}%"
                trip_stmt = trip_stmt.where(or_(
                    cast(Trip.origin, String).ilike(pattern),
                    cast(Trip.destinations, String).ilike(pattern),
                    Trip.pace.ilike(pattern),
                    Trip.budget.ilike(pattern),
                ))
            trips = (await db.execute(trip_stmt)).scalars().all()
            trip_ids = [trip.id for trip in trips]

            itinerary_stmt = select(TripItinerary)
            member_stmt = select(TripMember)
            if trip_ids:
                itinerary_stmt = itinerary_stmt.where(TripItinerary.trip_id.in_(trip_ids))
                member_stmt = member_stmt.where(TripMember.trip_id.in_(trip_ids))
            elif start or normalized_search or (planning_type and planning_type != "all") or (status and status != "all"):
                itineraries = []
                members = []
            if trip_ids or not (start or normalized_search or (planning_type and planning_type != "all") or (status and status != "all")):
                itineraries = (await db.execute(itinerary_stmt)).scalars().all()
                members = (await db.execute(member_stmt)).scalars().all()

            tickets = (await db.execute(select(SupportTicket))).scalars().all()
            subscriptions = (await db.execute(select(EmailSubscription))).scalars().all()
            cache_entries = (await db.execute(select(ApiCache))).scalars().all()
            photo_cache_entries = (await db.execute(select(PlacePhotoCache))).scalars().all()
            rate_usage = (await db.execute(select(RateLimitUsage))).scalars().all()
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to build admin analytics overview", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to build analytics overview: {e}")

    itinerary_by_trip = {itinerary.trip_id: itinerary for itinerary in itineraries}
    status_counts = Counter(_enum_value(trip.status) for trip in trips)
    planning_counts = Counter(_enum_value(trip.planning_type) for trip in trips)
    auth_counts = Counter(user.auth_provider or "unknown" for user in users)
    budget_counts = Counter(trip.budget or "Unknown" for trip in trips)
    pace_counts = Counter(trip.pace or "Unknown" for trip in trips)

    generated_statuses = {
        PlanStatus.GENERATED.value,
        PlanStatus.EDITING.value,
        PlanStatus.CURRENT.value,
        PlanStatus.COMPLETED.value,
    }
    generated_trips = sum(1 for trip in trips if _enum_value(trip.status) in generated_statuses)
    draft_trips = status_counts[PlanStatus.DRAFT.value]
    generating_trips = status_counts[PlanStatus.GENERATING.value]

    generated_itineraries = [
        itinerary for itinerary in itineraries
        if _enum_value(itinerary.status) == TripItineraryStatus.GENERATED.value
    ]
    trip_day_values = [
        days_value
        for trip in trips
        if (days_value := _trip_days(trip, itinerary_by_trip.get(trip.id))) is not None
    ]
    cost_values = [
        float(itinerary.cost)
        for itinerary in generated_itineraries
        if itinerary.cost is not None
    ]
    event_counts = [
        len(itinerary.events or [])
        for itinerary in generated_itineraries
    ]

    accepted_members = [
        member for member in members
        if member.invitation_status == TripInvitationStatus.ACCEPTED.value
    ]
    pending_members = [
        member for member in members
        if member.invitation_status == TripInvitationStatus.PENDING.value
    ]
    members_by_trip: dict[Any, int] = defaultdict(int)
    for member in accepted_members:
        members_by_trip[member.trip_id] += 1

    destination_counts: Counter[str] = Counter()
    for trip in trips:
        for destination in trip.destinations or []:
            city = _city_name(destination)
            if city:
                destination_counts[city] += 1

    series = _build_empty_series(start, now)
    if series:
        for user in users:
            key = _date_key(user.created_at)
            if key in series:
                series[key]["users"] += 1
        for trip in trips:
            key = _date_key(trip.created_at)
            if key in series:
                series[key]["trips"] += 1
                if _enum_value(trip.status) == PlanStatus.DRAFT.value:
                    series[key]["drafts"] += 1
        for itinerary in generated_itineraries:
            key = _date_key(itinerary.updated_at)
            if key in series:
                series[key]["generated"] += 1

    top_skus = Counter()
    for usage in rate_usage:
        top_skus[usage.sku] += usage.usage or 0

    recent_itineraries = sorted(
        generated_itineraries,
        key=lambda item: _sort_timestamp(item.updated_at or item.created_at),
        reverse=True,
    )[:8]

    total_users = len(users)
    google_users = auth_counts["google"]
    local_users = auth_counts["local"]
    verified_users = sum(1 for user in users if user.is_verified)
    total_trips = len(trips)

    return {
        "status_code": 200,
        "filters": {
            "days": days,
            "planning_type": planning_type or "all",
            "status": status or "all",
            "auth_provider": auth_provider or "all",
            "search": search or "",
            "start": _iso(start),
            "end": _iso(now),
        },
        "summary": {
            "total_users": total_users,
            "google_users": google_users,
            "local_users": local_users,
            "verified_users": verified_users,
            "new_users": sum(1 for user in users if user.is_new_user),
            "admin_users": sum(1 for user in users if user.is_admin),
            "total_trips": total_trips,
            "total_itineraries": len(itineraries),
            "generated_trips": generated_trips,
            "generated_itineraries": len(generated_itineraries),
            "remaining_drafts": draft_trips,
            "generating_trips": generating_trips,
            "conversion_rate": _pct(generated_trips, total_trips),
            "draft_rate": _pct(draft_trips, total_trips),
            "google_user_rate": _pct(google_users, total_users),
            "verification_rate": _pct(verified_users, total_users),
            "average_days_per_trip": _avg(trip_day_values),
            "average_trip_cost": _avg(cost_values),
            "average_events_per_itinerary": _avg(event_counts),
            "average_party_size": _avg([trip.adults + trip.children for trip in trips]),
        },
        "collaboration": {
            "accepted_members": len(accepted_members),
            "pending_invites": len(pending_members),
            "shared_trips": sum(1 for count in members_by_trip.values() if count > 1),
            "average_members_per_trip": _avg(list(members_by_trip.values())),
        },
        "operations": {
            "open_tickets": sum(1 for ticket in tickets if ticket.status == TicketStatus.OPEN),
            "unacknowledged_tickets": sum(1 for ticket in tickets if not ticket.acknowledged),
            "resolved_tickets": sum(1 for ticket in tickets if ticket.status == TicketStatus.RESOLVED),
            "email_subscriptions": len(subscriptions),
            "unsubscribed_emails": sum(1 for sub in subscriptions if sub.unsubscribed_at is not None),
            "api_cache_entries": len(cache_entries),
            "photo_cache_entries": len(photo_cache_entries),
            "rate_limit_usage_records": len(rate_usage),
        },
        "breakdowns": {
            "statuses": dict(status_counts),
            "planning_types": dict(planning_counts),
            "auth_providers": dict(auth_counts),
            "budgets": dict(budget_counts),
            "paces": dict(pace_counts),
            "top_destinations": [
                {"name": name, "count": count}
                for name, count in destination_counts.most_common(8)
            ],
            "top_rate_limit_skus": [
                {"sku": sku, "usage": usage}
                for sku, usage in top_skus.most_common(8)
            ],
        },
        "series": list(series.values()),
        "recent_itineraries": [
            {
                "id": str(itinerary.id),
                "trip_id": str(itinerary.trip_id),
                "title": itinerary.title,
                "origin": itinerary.origin,
                "destinations": itinerary.destinations,
                "days": itinerary.days,
                "cost": itinerary.cost,
                "status": _enum_value(itinerary.status),
                "updated_at": _iso(itinerary.updated_at),
            }
            for itinerary in recent_itineraries
        ],
    }
