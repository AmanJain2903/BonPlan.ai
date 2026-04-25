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
from app.services.rate_limiter.rate_limiter import get_rate_limiter

router = APIRouter()

class CreateRateLimitConfigBody(BaseModel):
    sku: str
    service: str
    description: Optional[str] = None
    provider: str
    limit: int
    period: Period
    scope: Scope

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

class DeleteRateLimitConfigBody(BaseModel):
    sku: Optional[str] = None
    sku_id: Optional[str] = None

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

@router.post("/create-rate-limit-config", response_model=dict)
async def create_rate_limit_config(data: CreateRateLimitConfigBody):
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

    async with Session() as db:
        try:
            existing_config = (await db.execute(select(RateLimitConfigs).where(RateLimitConfigs.sku == sku))).scalar_one_or_none()
            if existing_config:
                raise HTTPException(status_code=400, detail="Rate limit config already exists.")
            new_config = RateLimitConfigs(sku=sku, service=service, description=description, provider=provider, limit=limit, period=period, scope=scope)
            db.add(new_config)
            await db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create rate limit config: {e}")

    await get_rate_limiter().invalidate_config_cache()
    return {"message": "Rate limit config created successfully.", "status_code": 200}

@router.get("/get-rate-limit-config", response_model=dict)
async def get_rate_limit_config(sku: Optional[str] = None, sku_id: Optional[str] = None):
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
            raise HTTPException(status_code=500, detail=f"Failed to get rate limit config: {e}")
        
    config_dict = {
        "id": str(config.id),
        "sku": _titlelize_optional(config.sku),
        "raw_sku": config.sku,
        "service": config.service,
        "description": config.description,
        "provider": _titlelize_optional(config.provider),
        "limit": config.limit,
        "period": config.period.value,
        "scope": config.scope.value,
    }

    return {"message": "Rate limit config retrieved successfully.", "status_code": 200, "config": config_dict}

@router.put("/update-rate-limit-config", response_model=dict)
async def update_rate_limit_config(data: UpdateRateLimitConfigBody):
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
            await db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update rate limit config: {e}")

    await get_rate_limiter().invalidate_config_cache()
    return {"message": "Rate limit config updated successfully.", "status_code": 200}

@router.delete("/delete-rate-limit-config", response_model=dict)
async def delete_rate_limit_config(data: DeleteRateLimitConfigBody):
    sku = _format_for_insert(data.sku)
    sku_id = data.sku_id
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
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete rate limit config: {e}")
    await get_rate_limiter().invalidate_config_cache()
    return {"message": "Rate limit config deleted successfully.", "status_code": 200}

@router.get("/configs", response_model=dict)
async def get_all_configs():
    """Retrieve all rate limit configs for the dashboard."""
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
                } for c in configs
            ]
            return {"status_code": 200, "configs": config_list}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get configs: {e}")

@router.get("/usage", response_model=dict)
async def get_all_usage(
    scope: Optional[Scope] = Query(None, description="Filter by scope (global or user)"),
    period_bucket: Optional[str] = Query(None, description="Filter by specific period bucket")
):
    """Retrieve rate limit usage records, optionally filtered."""
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
            raise HTTPException(status_code=500, detail=f"Failed to get usage: {e}")
