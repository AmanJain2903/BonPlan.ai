# backend/app/api/v1/endpoints/rate_limiting.py

"""
This file contains the rate limiting endpoints for the BonPlan.ai backend.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, or_

from app.database.database import Session
from app.database.models.rateLimitConfigs import RateLimitConfigs
from app.database.models.rateLimitUsage import RateLimitUsage
from app.database.models.rateLimitConfigs import Period, Scope
from typing import Optional

class CreateRateLimitConfigBody(BaseModel):
    sku: str
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
    description: Optional[str] = None
    provider: Optional[str] = None
    limit: Optional[int] = None
    period: Optional[Period] = None
    scope: Optional[Scope] = None

class DeleteRateLimitConfigBody(BaseModel):
    sku: Optional[str] = None
    sku_id: Optional[str] = None

router = APIRouter()


def _normalize_optional_lower(value: Optional[str]) -> Optional[str]:
    return value.lower() if isinstance(value, str) else None

"""
Create a rate limit config endpoint
"""
@router.post("/create-rate-limit-config", response_model=dict)
async def create_rate_limit_config(data: CreateRateLimitConfigBody):
    sku = _normalize_optional_lower(data.sku)
    if not sku:
        raise HTTPException(status_code=400, detail="SKU is required.")
    provider = _normalize_optional_lower(data.provider)
    if not provider:
        raise HTTPException(status_code=400, detail="Provider is required.")
    limit = data.limit
    if limit is None or limit < 0:
        raise HTTPException(status_code=400, detail="Limit must be a non-negative integer.")
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
            new_config = RateLimitConfigs(sku=sku, description=description, provider=provider, limit=limit, period=period, scope=scope)
            db.add(new_config)
            await db.commit()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create rate limit config: {e}")

    return {"message": "Rate limit config created successfully.", "status_code": 200}

"""
Get a rate limit config endpoint
"""
@router.get("/get-rate-limit-config", response_model=dict)
async def get_rate_limit_config(data: GetRateLimitConfigBody):
    sku = _normalize_optional_lower(data.sku)
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
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get rate limit config: {e}")
        
    config = {
        "sku": config.sku.title(),
        "description": config.description,
        "provider": config.provider.title(),
        "limit": config.limit,
        "period": config.period.value,
        "scope": config.scope.value,
    }

    return {"message": "Rate limit config retrieved successfully.", "status_code": 200, "config": config}

"""
Update a rate limit config endpoint
"""
@router.put("/update-rate-limit-config", response_model=dict)
async def update_rate_limit_config(data: UpdateRateLimitConfigBody):
    sku = _normalize_optional_lower(data.sku)
    sku_id = data.sku_id
    provider = _normalize_optional_lower(data.provider)
    limit = data.limit
    period = data.period
    scope = data.scope
    description = data.description
    if not sku and not sku_id:
        raise HTTPException(status_code=400, detail="SKU name or SKU ID is required.")
    if limit is not None and limit < 0:
        raise HTTPException(status_code=400, detail="Limit must be a non-negative integer.")

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

    return {"message": "Rate limit config updated successfully.", "status_code": 200}

"""
Delete a rate limit config endpoint
"""
@router.delete("/delete-rate-limit-config", response_model=dict)
async def delete_rate_limit_config(data: DeleteRateLimitConfigBody):
    sku = _normalize_optional_lower(data.sku)
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
    return {"message": "Rate limit config deleted successfully.", "status_code": 200}