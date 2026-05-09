# backend/app/services/rate_limiter/limit_alerts.py

import html
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database.database import Session
from app.database.models.rateLimitAlertEventsTable import RateLimitAlertEvent
from app.database.models.rateLimitAlertSettingsTable import RateLimitAlertSettings
from app.database.models.rateLimitConfigs import RateLimitConfigs
from app.database.models.usersTable import User
from app.logging import get_rate_limiter_logger
from app.utils.emailVerification import SYSTEM_EMAIL_FROM, bonplan_inline_images, render_email_layout, send_email

logger = get_rate_limiter_logger("limit_alerts")

DEFAULT_ALERT_THRESHOLDS = [80, 90, 100]


def normalize_thresholds(thresholds: list[int]) -> list[int]:
    cleaned = sorted({int(value) for value in thresholds if 1 <= int(value) <= 100})
    if not cleaned:
        raise ValueError("At least one threshold between 1 and 100 is required.")
    return cleaned


async def get_or_create_alert_settings(db) -> RateLimitAlertSettings:
    settings = (
        await db.execute(select(RateLimitAlertSettings).where(RateLimitAlertSettings.key == "global"))
    ).scalar_one_or_none()
    if settings:
        return settings
    settings = RateLimitAlertSettings(key="global", enabled=True, thresholds=DEFAULT_ALERT_THRESHOLDS)
    db.add(settings)
    await db.flush()
    return settings


def admin_alert_email(first_name: str | None) -> str:
    safe = re.sub(r"[^a-z0-9]+", "", (first_name or "admin").strip().lower()) or "admin"
    return f"admin-{safe}@bonplanai.com"


def _owner_label(scope: str, user_id: Optional[UUID]) -> str:
    if scope == "user" and user_id:
        return str(user_id)
    return "global"


def _format_percent(usage: int, limit: int) -> str:
    if limit <= 0:
        return "0%"
    return f"{usage / limit * 100:.1f}%"


def format_sku_name(sku: str) -> str:
    return " ".join(part.capitalize() for part in sku.split("_") if part)


def _alert_email_body(
    *,
    config: RateLimitConfigs,
    threshold: int,
    usage: int,
    limit: int,
    scope: str,
    period: str,
    period_bucket: str,
    user_id: Optional[UUID],
) -> str:
    sku = html.escape(format_sku_name(config.sku))
    service = html.escape(config.service)
    provider = html.escape(config.provider)
    description = html.escape(config.description or "No description provided.")
    owner = html.escape(_owner_label(scope, user_id))
    body = f"""
    <p style="margin:0 0 16px;">A BonPlan.ai SKU crossed a configured usage alert threshold.</p>
    <div style="border:1px solid rgba(102,252,241,0.24);border-radius:14px;background:rgba(102,252,241,0.06);padding:16px;margin:20px 0;">
      <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#66FCF1;font-weight:700;margin-bottom:6px;">Threshold</div>
      <div style="font-size:26px;color:#ffffff;font-weight:800;">{threshold}% reached</div>
      <div style="font-size:13px;color:rgba(197,198,199,0.8);margin-top:6px;">{usage:,} of {limit:,} used ({_format_percent(usage, limit)})</div>
    </div>
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#D6D8DA;margin:18px 0;">
      <tr><td style="padding:8px 0;color:rgba(197,198,199,0.68);">SKU</td><td style="padding:8px 0;color:#ffffff;font-weight:700;text-align:right;">{sku}</td></tr>
      <tr><td style="padding:8px 0;color:rgba(197,198,199,0.68);">Service</td><td style="padding:8px 0;text-align:right;">{service}</td></tr>
      <tr><td style="padding:8px 0;color:rgba(197,198,199,0.68);">Provider</td><td style="padding:8px 0;text-align:right;">{provider}</td></tr>
      <tr><td style="padding:8px 0;color:rgba(197,198,199,0.68);">Scope</td><td style="padding:8px 0;text-align:right;">{html.escape(scope)}</td></tr>
      <tr><td style="padding:8px 0;color:rgba(197,198,199,0.68);">Owner</td><td style="padding:8px 0;text-align:right;">{owner}</td></tr>
      <tr><td style="padding:8px 0;color:rgba(197,198,199,0.68);">Period</td><td style="padding:8px 0;text-align:right;">{html.escape(period)} / {html.escape(period_bucket)}</td></tr>
    </table>
    <p style="margin:0 0 16px;color:rgba(214,216,218,0.82);">{description}</p>
    """
    return render_email_layout(
        title=f"SKU usage alert: {sku}",
        preheader=f"{sku} reached {threshold}% of its {period} limit.",
        eyebrow="System alert",
        body_html=body,
        footer_html="This operational alert was sent to BonPlan.ai admins from noreply-system@bonplanai.com.",
    )


async def maybe_send_rate_limit_alert(
    *,
    sku_id: UUID,
    sku: str,
    usage: int,
    limit: int,
    scope: str,
    period: str,
    period_bucket: str,
    user_id: Optional[UUID] = None,
) -> None:
    if limit <= 0 or usage <= 0:
        return

    async with Session() as db:
        settings = await get_or_create_alert_settings(db)
        if not settings.enabled:
            await db.commit()
            return

        try:
            thresholds = normalize_thresholds(settings.thresholds or DEFAULT_ALERT_THRESHOLDS)
        except ValueError:
            thresholds = DEFAULT_ALERT_THRESHOLDS

        crossed = [threshold for threshold in thresholds if usage / limit * 100 >= threshold]
        if not crossed:
            await db.commit()
            return

        config = (
            await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.id == sku_id))
        ).scalar_one_or_none()
        if not config:
            await db.commit()
            return

        admins = (await db.execute(select(User).where(User.is_admin == True))).scalars().all()
        if not admins:
            logger.warning("No admins found for rate-limit alert", sku=sku)
            await db.commit()
            return

        usage_owner = _owner_label(scope, user_id)
        for threshold in crossed:
            existing = (
                await db.execute(
                    select(RateLimitAlertEvent).where(
                        RateLimitAlertEvent.sku_id == sku_id,
                        RateLimitAlertEvent.period_bucket == period_bucket,
                        RateLimitAlertEvent.usage_owner == usage_owner,
                        RateLimitAlertEvent.threshold_percent == threshold,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue

            event = RateLimitAlertEvent(
                sku_id=sku_id,
                sku=sku,
                period_bucket=period_bucket,
                usage_owner=usage_owner,
                threshold_percent=threshold,
                usage=usage,
                limit=limit,
            )
            db.add(event)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                return

            body = _alert_email_body(
                config=config,
                threshold=threshold,
                usage=usage,
                limit=limit,
                scope=scope,
                period=period,
                period_bucket=period_bucket,
                user_id=user_id,
            )
            for admin in admins:
                await send_email(
                    to_email=admin_alert_email(admin.first_name),
                    subject=f"BonPlan.ai system alert - {format_sku_name(config.sku)} reached {threshold}%",
                    body=body,
                    from_email=SYSTEM_EMAIL_FROM,
                    inline_images=bonplan_inline_images(),
                )

        await db.commit()
