# backend/app/api/v1/endpoints/rate_limiting_admin.py

"""
Admin Rate-limiting endpoints for the BonPlan.ai backend.

Provides CRUD for `rate_limit_configs` and queries for `rate_limit_usage`.
"""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_

from app.database.database import Session
from app.database.models.rateLimitConfigs import RateLimitConfigs, Period, Scope
from app.database.models.rateLimitUsage import RateLimitUsage
from app.database.models.usersTable import User
import jwt
from app.core.config import settings
from app.logging import get_api_logger
from app.services.rate_limiter.limit_alerts import DEFAULT_ALERT_THRESHOLDS, get_or_create_alert_settings, normalize_thresholds
from app.services.rate_limiter.rate_limiter import get_rate_limiter

logger = get_api_logger("api.rate_limiting_admin")
router = APIRouter()

async def _verify_admin(token: str):
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

class CreateRateLimitConfigBody(BaseModel):
    sku: str
    service: str
    description: Optional[str] = None
    provider: str
    limit: int
    period: Period
    scope: Scope
    # Per-SKU reset anchor (interpreted in RATE_LIMITER_RESET_TZ).
    # Defaults reproduce the historic global behavior: midnight on the 1st.
    reset_minute: Optional[int] = 0
    reset_hour: Optional[int] = 0
    reset_day: Optional[int] = 1
    reset_month: Optional[int] = 1

class GetRateLimitConfigBody(BaseModel):
    sku: Optional[str] = None
    sku_id: Optional[str] = None

class UpdateRateLimitConfigBody(BaseModel):
    sku: Optional[str] = None
    sku_id: Optional[str] = None
    service: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None
    limit: Optional[int] = None
    period: Optional[Period] = None
    scope: Optional[Scope] = None
    reset_minute: Optional[int] = None
    reset_hour: Optional[int] = None
    reset_day: Optional[int] = None
    reset_month: Optional[int] = None


def _validate_reset_fields(
    period: Optional[Period],
    reset_minute: Optional[int],
    reset_hour: Optional[int],
    reset_day: Optional[int],
    reset_month: Optional[int],
) -> None:
    """
    Range-check whatever reset_* fields are supplied. We don't require a
    period to be present — partial updates may only touch hour/minute, etc.
    Day-of-month >28 is allowed; the limiter clamps to month length at runtime.
    """
    if reset_minute is not None and not (0 <= reset_minute <= 59):
        raise HTTPException(status_code=400, detail="reset_minute must be 0–59.")
    if reset_hour is not None and not (0 <= reset_hour <= 23):
        raise HTTPException(status_code=400, detail="reset_hour must be 0–23.")
    if reset_day is not None:
        if period == Period.WEEKLY and not (1 <= reset_day <= 7):
            raise HTTPException(status_code=400, detail="reset_day for weekly must be 1 (Mon) – 7 (Sun).")
        if period in (Period.MONTHLY, Period.YEARLY) and not (1 <= reset_day <= 31):
            raise HTTPException(status_code=400, detail="reset_day must be 1–31.")
        if period is None and not (1 <= reset_day <= 31):
            raise HTTPException(status_code=400, detail="reset_day must be 1–31.")
    if reset_month is not None and not (1 <= reset_month <= 12):
        raise HTTPException(status_code=400, detail="reset_month must be 1–12.")

class DeleteRateLimitConfigBody(BaseModel):
    sku: Optional[str] = None
    sku_id: Optional[str] = None

class UpdateAlertSettingsBody(BaseModel):
    enabled: bool = True
    thresholds: List[int]

def _titlelize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("_", " ")
        return value.title()
    return None

def _format_for_insert(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.lower().strip().replace(" ", "_")

def _settings_response(settings) -> dict:
    thresholds = settings.thresholds or DEFAULT_ALERT_THRESHOLDS
    try:
        thresholds = normalize_thresholds(thresholds)
    except ValueError:
        thresholds = DEFAULT_ALERT_THRESHOLDS
    return {
        "enabled": bool(settings.enabled),
        "thresholds": thresholds,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }

@router.post("/create-rate-limit-config", response_model=dict)
async def create_rate_limit_config(token: str, data: CreateRateLimitConfigBody):
    await _verify_admin(token)
    sku = _format_for_insert(data.sku)
    if not sku:
        raise HTTPException(status_code=400, detail="SKU is required.")
    service = data.service
    if not service:
        raise HTTPException(status_code=400, detail="Service is required.")
    provider = _format_for_insert(data.provider)
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required.")
    limit = data.limit
    if limit is None or limit < 0:
        if limit != -1: # allow unlimited
            raise HTTPException(status_code=400, detail="Limit must be a non-negative integer or -1 for unlimited.")
    period = data.period
    if not period:
        raise HTTPException(status_code=400, detail="Period is required.")
    scope = data.scope
    if not scope:
        raise HTTPException(status_code=400, detail="Scope is required.")
    description = data.description
    if not description:
        description = ""

    _validate_reset_fields(period, data.reset_minute, data.reset_hour, data.reset_day, data.reset_month)

    async with Session() as db:
        try:
            existing_config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.sku == sku))).scalar_one_or_none()
            if existing_config:
                raise HTTPException(status_code=400, detail="Rate limit config already exists.")
            new_config = RateLimitConfigs(
                sku=sku, service=service, description=description, provider=provider,
                limit=limit, period=period, scope=scope,
                reset_minute=data.reset_minute if data.reset_minute is not None else 0,
                reset_hour=data.reset_hour if data.reset_hour is not None else 0,
                reset_day=data.reset_day if data.reset_day is not None else 1,
                reset_month=data.reset_month if data.reset_month is not None else 1,
            )
            db.add(new_config)
            await db.commit()
            logger.info("Rate limit config created successfully", sku=sku)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to create rate limit config", sku=sku, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to create rate limit config: {e}")

    await get_rate_limiter().invalidate_config_cache()
    return {"message": "Rate limit config created successfully.", "status_code": 200}

@router.get("/get-rate-limit-config", response_model=dict)
async def get_rate_limit_config(token: str, sku: Optional[str] = None, sku_id: Optional[str] = None):
    await _verify_admin(token)
    if not sku and not sku_id:
        raise HTTPException(status_code=400, detail="SKU name or SKU ID is required.")

    async with Session() as db:
        try:
            if sku and sku_id:
                config = (await db.execute(select(RateLimitConfigs).where(or_(RateLimitConfigs.sku == _format_for_insert(sku), RateLimitConfigs.id == sku_id)))).scalar_one_or_none()
            elif sku:
                config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.sku == _format_for_insert(sku)))).scalar_one_or_none()
            else:
                config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.id == sku_id))).scalar_one_or_none()
            if not config:
                raise HTTPException(status_code=404, detail="Rate limit config not found.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to get rate limit config", sku=sku, sku_id=sku_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get rate limit config: {e}")
        
    config_dict = {
        "id": str(config.id),
        "sku": _titlelize_optional(config.sku),
        "service": config.service,
        "description": config.description,
        "provider": _titlelize_optional(config.provider),
        "limit": config.limit,
        "period": config.period.value,
        "scope": config.scope.value,
        "reset_minute": config.reset_minute,
        "reset_hour": config.reset_hour,
        "reset_day": config.reset_day,
        "reset_month": config.reset_month,
    }

    return {"message": "Rate limit config retrieved successfully.", "status_code": 200, "config": config_dict}

@router.put("/update-rate-limit-config", response_model=dict)
async def update_rate_limit_config(token: str, data: UpdateRateLimitConfigBody):
    await _verify_admin(token)
    sku = _format_for_insert(data.sku)
    sku_id = data.sku_id
    service = data.service
    provider = _format_for_insert(data.provider)
    limit = data.limit
    period = data.period
    scope = data.scope
    description = data.description
    if not sku and not sku_id:
        raise HTTPException(status_code=400, detail="SKU name or SKU ID is required.")
    if limit is not None and limit < 0 and limit != -1:
        raise HTTPException(status_code=400, detail="Limit must be a non-negative integer or -1 for unlimited.")

    _validate_reset_fields(period, data.reset_minute, data.reset_hour, data.reset_day, data.reset_month)

    async with Session() as db:
        try:
            if sku and sku_id:
                config = (await db.execute(select(RateLimitConfigs).where(or_(RateLimitConfigs.sku == sku, RateLimitConfigs.id == sku_id)))).scalar_one_or_none()
            elif sku:
                config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.sku == sku))).scalar_one_or_none()
            else:
                config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.id == sku_id))).scalar_one_or_none()
            if not config:
                raise HTTPException(status_code=404, detail="Rate limit config not found.")
            if sku:
                config.sku = sku
            if service:
                config.service = service
            if description is not None:
                config.description = description
            if provider:
                config.provider = provider
            if limit is not None:
                config.limit = limit
            if period:
                config.period = period
            if scope:
                config.scope = scope
            if data.reset_minute is not None:
                config.reset_minute = data.reset_minute
            if data.reset_hour is not None:
                config.reset_hour = data.reset_hour
            if data.reset_day is not None:
                config.reset_day = data.reset_day
            if data.reset_month is not None:
                config.reset_month = data.reset_month
            await db.commit()
            logger.info("Rate limit config updated successfully", sku=sku if sku else config.sku, sku_id=sku_id if sku_id else config.id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to update rate limit config", sku=sku if sku else config.sku, sku_id=sku_id if sku_id else config.id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to update rate limit config: {e}")

    await get_rate_limiter().invalidate_config_cache()
    return {"message": "Rate limit config updated successfully.", "status_code": 200}

@router.delete("/delete-rate-limit-config", response_model=dict)
async def delete_rate_limit_config(token: str, sku: Optional[str] = Query(None), sku_id: Optional[str] = Query(None)):
    await _verify_admin(token)
    sku = _format_for_insert(sku)
    if not sku and not sku_id:
        raise HTTPException(status_code=400, detail="SKU name or SKU ID is required.")

    async with Session() as db:
        try:
            if sku and sku_id:
                config = (await db.execute(select(RateLimitConfigs).where(or_(RateLimitConfigs.sku == sku, RateLimitConfigs.id == sku_id)))).scalar_one_or_none()
            elif sku:
                config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.sku == sku))).scalar_one_or_none()
            else:
                config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.id == sku_id))).scalar_one_or_none()
            if not config:
                raise HTTPException(status_code=404, detail="Rate limit config not found.")
            await db.delete(config)
            await db.commit()
            logger.info("Rate limit config deleted successfully", sku=sku if sku else config.sku, sku_id=sku_id if sku_id else config.id)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to delete rate limit config", sku=sku if sku else config.sku, sku_id=sku_id if sku_id else config.id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to delete rate limit config: {e}")
    await get_rate_limiter().invalidate_config_cache()
    return {"message": "Rate limit config deleted successfully.", "status_code": 200}

@router.get("/configs", response_model=dict)
async def get_all_configs(token: str):
    """Retrieve all rate limit configs for the dashboard."""
    await _verify_admin(token)
    async with Session() as db:
        try:
            configs = (await db.execute(select(RateLimitConfigs).order_by(RateLimitConfigs.updated_at.desc()))).scalars().all()
            config_list = [
                {
                    "id": str(c.id),
                    "sku": _titlelize_optional(c.sku),
                    "service": c.service,
                    "description": c.description,
                    "provider": _titlelize_optional(c.provider),
                    "limit": c.limit,
                    "period": c.period.value,
                    "scope": c.scope.value,
                    "reset_minute": c.reset_minute,
                    "reset_hour": c.reset_hour,
                    "reset_day": c.reset_day,
                    "reset_month": c.reset_month,
                } for c in configs
            ]
            return {"status_code": 200, "configs": config_list}
        except Exception as e:
            logger.error("Failed to get rate limit configs", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get configs: {e}")

@router.get("/usage", response_model=dict)
async def get_all_usage(
    token: str,
    scope: Optional[Scope] = Query(None, description="Filter by scope (global or user)"),
    period_bucket: Optional[str] = Query(None, description="Filter by specific period bucket")
):
    """Retrieve rate limit usage records, optionally filtered."""
    await _verify_admin(token)
    async with Session() as db:
        try:
            # We need to join with configs to filter by scope
            stmt = select(RateLimitUsage, RateLimitConfigs, User).join(
                RateLimitConfigs, RateLimitUsage.sku_id == RateLimitConfigs.id
            ).outerjoin(
                User, RateLimitUsage.user_id == User.id
            )
            
            if scope:
                stmt = stmt.where(RateLimitConfigs.scope == scope)
                
            if period_bucket:
                stmt = stmt.where(RateLimitUsage.period_bucket.like(f"%{period_bucket}%"))

            stmt = stmt.order_by(RateLimitUsage.updated_at.desc())

            results = (await db.execute(stmt)).all()
            
            usage_list = []
            for usage, config, user in results:
                user_name = f"{user.first_name} {user.last_name}" if user else "Global / Unknown"
                usage_list.append({
                    "id": str(usage.id),
                    "sku": _titlelize_optional(usage.sku),
                    "user_id": str(usage.user_id),
                    "user_name": user_name,
                    "period_bucket": usage.period_bucket,
                    "usage": usage.usage,
                    "limit": config.limit,
                    "scope": config.scope.value,
                    "period": config.period.value,
                    "updated_at": usage.updated_at.isoformat() if usage.updated_at else None,
                })
            return {"status_code": 200, "usage": usage_list}
        except Exception as e:
            logger.error("Failed to get rate limit usages", scope=scope, period_bucket=period_bucket, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get usage: {e}")

@router.get("/alert-settings", response_model=dict)
async def get_alert_settings(token: str):
    await _verify_admin(token)
    async with Session() as db:
        try:
            settings = await get_or_create_alert_settings(db)
            await db.commit()
            return {"status_code": 200, "settings": _settings_response(settings)}
        except Exception as e:
            logger.error("Failed to get rate limit alert settings", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get alert settings: {e}")


@router.put("/alert-settings", response_model=dict)
async def update_alert_settings(token: str, data: UpdateAlertSettingsBody):
    await _verify_admin(token)
    try:
        thresholds = normalize_thresholds(data.thresholds)
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    async with Session() as db:
        try:
            settings = await get_or_create_alert_settings(db)
            settings.enabled = data.enabled
            settings.thresholds = thresholds
            await db.commit()
            await db.refresh(settings)
            return {"status_code": 200, "settings": _settings_response(settings)}
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to update rate limit alert settings", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to update alert settings: {e}")
