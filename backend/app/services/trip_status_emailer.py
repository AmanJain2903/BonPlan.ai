# backend/app/services/trip_status_emailer.py

import asyncio
import html
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.database import Session
from app.database.models.emailSubscriptionsTable import EmailSubscription
from app.database.models.tripEmailNotificationsTable import TripEmailNotification
from app.database.models.tripsTable import PlanStatus, Trip
from app.database.models.usersTable import User
from app.database.models.tripItinerariesTable import TripItinerary
from app.logging import get_app_logger
from app.utils.emailVerification import (
    TRIP_EMAIL_FROM,
    bonplan_inline_images,
    render_email_layout,
    send_email,
)

logger = get_app_logger("trip_status_emailer")

TRIP_STATUS_EMAIL_CATEGORY = "trip_status"
KIND_DRAFT = "draft_reminder"
KIND_CURRENT = "current_started"
KIND_COMPLETED = "completed"
_INTERVAL_SECONDS = 15 * 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime:
    if value is None:
        return _now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _date_label(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("formatted", "label", "date", "localDate"):
            if value.get(key):
                return str(value[key])
        if value.get("utcTimestamp"):
            try:
                return datetime.fromtimestamp(int(value["utcTimestamp"]), timezone.utc).strftime("%b %-d, %Y")
            except Exception:
                return "your travel date"
    return "your travel date"


def _trip_title(trip: Trip, tripItinerary: TripItinerary) -> str:
    if tripItinerary:
        return tripItinerary.title
    destinations = trip.destinations or []
    names = []
    for destination in destinations:
        if isinstance(destination, dict):
            name = destination.get("name") or destination.get("description") or destination.get("city")
            if name:
                names.append(str(name))
    if names:
        return " + ".join(names[:2])
    return "your BonPlan trip"


def _unsubscribe_url(token: str) -> str:
    return f"{settings.BACKEND_URL}/api/v1/email-preferences/unsubscribe/{token}"


def _draft_next_delay(sent_count: int) -> timedelta:
    return timedelta(hours=24 + (sent_count * 12))


async def _get_or_create_subscription(db, user: User) -> EmailSubscription:
    existing = (
        await db.execute(
            select(EmailSubscription).where(
                EmailSubscription.user_id == user.id,
                EmailSubscription.category == TRIP_STATUS_EMAIL_CATEGORY,
            )
        )
    ).scalar_one_or_none()
    if existing:
        if existing.email != user.email:
            existing.email = user.email
        return existing

    subscription = EmailSubscription(
        user_id=user.id,
        email=user.email,
        category=TRIP_STATUS_EMAIL_CATEGORY,
        token=secrets.token_urlsafe(32),
    )
    db.add(subscription)
    await db.flush()
    return subscription


def _footer(unsubscribe_url: str) -> str:
    return f"""
    You are receiving trip status emails from BonPlan.ai.
    <a href="{html.escape(unsubscribe_url, quote=True)}" style="color:#66FCF1;text-decoration:none;">Unsubscribe</a>
    from these reminders and trip status updates.
    """


def _draft_email(user: User, trip: Trip, tripItinerary: TripItinerary, unsubscribe_url: str) -> tuple[str, str]:
    trip_title = html.escape(_trip_title(trip, tripItinerary))
    body = f"""
    <p style="margin:0 0 14px;">Hi {html.escape(user.first_name or "there")},</p>
    <p style="margin:0 0 16px;">Your draft for <strong style="color:#ffffff;">{trip_title}</strong> is still waiting.</p>
    <p style="margin:0 0 18px;">Start generation when you are ready and BonPlan.ai will turn your saved preferences into a complete itinerary.</p>
    """
    html_body = render_email_layout(
        title="Ready to generate your trip?",
        preheader="Your BonPlan.ai draft is ready for itinerary generation.",
        eyebrow="Draft reminder",
        body_html=body,
        cta_label="Open Draft",
        cta_url=settings.FRONTEND_URL,
        footer_html=_footer(unsubscribe_url),
    )
    return "BonPlan.ai - Your draft is ready to generate", html_body


def _current_email(user: User, trip: Trip, tripItinerary: TripItinerary, unsubscribe_url: str) -> tuple[str, str]:
    trip_title = html.escape(_trip_title(trip, tripItinerary))
    start = html.escape(_date_label(trip.start_date))
    body = f"""
    <p style="margin:0 0 14px;">Hi {html.escape(user.first_name or "there")},</p>
    <p style="margin:0 0 16px;">Your trip <strong style="color:#ffffff;">{trip_title}</strong> has begun.</p>
    <div style="border:1px solid rgba(102,252,241,0.24);border-radius:14px;background:rgba(102,252,241,0.06);padding:16px;margin:20px 0;">
      <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#66FCF1;font-weight:700;margin-bottom:6px;">Start date</div>
      <div style="font-size:18px;color:#ffffff;font-weight:700;">{start}</div>
    </div>
    <p style="margin:0 0 18px;">Your itinerary is ready to keep close while you travel.</p>
    """
    html_body = render_email_layout(
        title="Your trip has started",
        preheader="Your BonPlan.ai trip is now current.",
        eyebrow="Trip started",
        body_html=body,
        cta_label="Open Itinerary",
        cta_url=settings.FRONTEND_URL,
        footer_html=_footer(unsubscribe_url),
    )
    return "BonPlan.ai - Your trip has started", html_body


def _completed_email(user: User, trip: Trip, tripItinerary: TripItinerary, unsubscribe_url: str) -> tuple[str, str]:
    trip_title = html.escape(_trip_title(trip, tripItinerary))
    end = html.escape(_date_label(trip.end_date))
    body = f"""
    <p style="margin:0 0 14px;">Hi {html.escape(user.first_name or "there")},</p>
    <p style="margin:0 0 16px;">Your trip <strong style="color:#ffffff;">{trip_title}</strong> is now complete.</p>
    <div style="border:1px solid rgba(102,252,241,0.24);border-radius:14px;background:rgba(102,252,241,0.06);padding:16px;margin:20px 0;">
      <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#66FCF1;font-weight:700;margin-bottom:6px;">Completed after</div>
      <div style="font-size:18px;color:#ffffff;font-weight:700;">{end}</div>
    </div>
    <p style="margin:0 0 18px;">Your itinerary remains saved in BonPlan.ai whenever you want to revisit it or use it as a starting point.</p>
    """
    html_body = render_email_layout(
        title="Your trip is complete",
        preheader="Your BonPlan.ai trip has been marked complete.",
        eyebrow="Trip completed",
        body_html=body,
        cta_label="View Trip",
        cta_url=settings.FRONTEND_URL,
        footer_html=_footer(unsubscribe_url),
    )
    return "BonPlan.ai - Your trip is complete", html_body


def _message_for(kind: str, user: User, trip: Trip, tripItinerary: TripItinerary, unsubscribe_url: str) -> tuple[str, str]:
    if kind == KIND_DRAFT:
        return _draft_email(user, trip, tripItinerary, unsubscribe_url)
    if kind == KIND_CURRENT:
        return _current_email(user, trip, tripItinerary, unsubscribe_url)
    if kind == KIND_COMPLETED:
        return _completed_email(user, trip, tripItinerary, unsubscribe_url)
    raise ValueError(f"Unknown trip email kind: {kind}")


async def _send_and_track(db, *, trip: Trip, tripItinerary: TripItinerary, user: User, kind: str, existing: TripEmailNotification | None) -> bool:
    subscription = await _get_or_create_subscription(db, user)
    if subscription.unsubscribed_at is not None:
        return False

    subject, body = _message_for(kind, user, trip, tripItinerary, _unsubscribe_url(subscription.token))
    await send_email(
        to_email=user.email,
        subject=subject,
        body=body,
        from_email=TRIP_EMAIL_FROM,
        inline_images=bonplan_inline_images(),
    )

    now = _now()
    if existing is None:
        existing = TripEmailNotification(trip_id=trip.id, user_id=user.id, kind=kind, sent_count=0)
        db.add(existing)

    existing.sent_count = (existing.sent_count or 0) + 1
    existing.last_sent_at = now
    existing.next_send_at = now + _draft_next_delay(existing.sent_count) if kind == KIND_DRAFT else None
    await db.commit()
    return True


async def run_trip_status_email_update() -> None:
    now = _now()
    sent = 0
    async with Session() as db:
        rows = (
            await db.execute(
                select(Trip, TripItinerary, User)
                .join(User, Trip.owner_id == User.id)
                .join(TripItinerary, Trip.id == TripItinerary.trip_id)
                .where(Trip.status.in_([PlanStatus.DRAFT, PlanStatus.CURRENT, PlanStatus.COMPLETED]))
            )
        ).all()

        for trip, tripItinerary, user in rows:
            try:
                kind = {
                    PlanStatus.DRAFT: KIND_DRAFT,
                    PlanStatus.CURRENT: KIND_CURRENT,
                    PlanStatus.COMPLETED: KIND_COMPLETED,
                }.get(trip.status)
                if not kind:
                    continue

                notification = (
                    await db.execute(
                        select(TripEmailNotification).where(
                            TripEmailNotification.trip_id == trip.id,
                            TripEmailNotification.kind == kind,
                        )
                    )
                ).scalar_one_or_none()

                if kind in (KIND_CURRENT, KIND_COMPLETED) and notification and notification.sent_count > 0:
                    continue

                if kind == KIND_DRAFT:
                    if notification:
                        if notification.next_send_at and _as_aware(notification.next_send_at) > now:
                            continue
                    else:
                        anchor = max(_as_aware(trip.created_at), _as_aware(trip.updated_at))
                        if anchor + timedelta(hours=24) > now:
                            continue

                if await _send_and_track(db, trip=trip, tripItinerary=tripItinerary, user=user, kind=kind, existing=notification):
                    sent += 1
            except IntegrityError:
                await db.rollback()
            except Exception as e:
                await db.rollback()
                logger.warning("Trip status email failed", trip_id=str(trip.id), tripItinerary_id=str(tripItinerary.id), user_id=str(user.id), error=str(e))

    if sent:
        logger.info("Trip status emails sent", count=sent)


async def trip_status_email_task() -> None:
    logger.info("Trip status email task started")
    while True:
        await run_trip_status_email_update()
        await asyncio.sleep(_INTERVAL_SECONDS)
