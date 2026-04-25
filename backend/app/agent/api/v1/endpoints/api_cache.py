# backend/app/agent/api/v1/endpoints/api_cache.py

"""
This file contains the API cache endpoints for the agent.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.database.database import Session
from app.database.models.apiCacheTable import ApiCache
from app.logging import get_api_logger

logger = get_api_logger("agent.api_cache")
router = APIRouter()


class ApiCacheInsertBody(BaseModel):
    cache_key: str
    cache_value: dict


"""
Insert API cache endpoint
"""
@router.post("/insert", response_model=dict)
async def insert_api_cache(body: ApiCacheInsertBody):
    cache_key = body.cache_key
    cache_value = body.cache_value
    if not cache_key or not cache_value:
        raise HTTPException(status_code=400, detail="Cache key and cache value are required.")
    if not isinstance(cache_value, dict):
        raise HTTPException(status_code=400, detail="Cache value must be a dictionary.")
    if not isinstance(cache_key, str):
        raise HTTPException(status_code=400, detail="Cache key must be a string.")

    async with Session() as db:
        try:
            existing_cache = (await db.execute(
                select(ApiCache).where(ApiCache.cache_key == cache_key)
            )).scalar_one_or_none()
            if existing_cache is not None:
                await db.delete(existing_cache)
            new_cache = ApiCache(cache_key=cache_key, cache_value=cache_value)
            db.add(new_cache)
            await db.commit()
            return {"message": "API cache inserted successfully.", "status_code": 200}
        except Exception as e:
            await db.rollback()
            logger.exception("Failed to insert API cache", cache_key=cache_key, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to insert API cache: {e}")


"""
Retrieve API cache endpoint
"""
@router.get("/retrieve", response_model=dict)
async def retrieve_api_cache(
    cache_key: str = Query(..., description="Cache lookup key"),
    expires_in: int = Query(default=1, ge=1, le=365, description="Cache expiration time in days"),
):
    async with Session() as db:
        try:
            cache = (await db.execute(
                select(ApiCache).where(ApiCache.cache_key == cache_key)
            )).scalar_one_or_none()
            if not cache:
                return {"message": "API cache not found.", "status_code": 404}
            created_at = cache.created_at
            if created_at is not None and created_at < datetime.now(timezone.utc) - timedelta(days=expires_in):
                await db.delete(cache)
                await db.commit()
                return {"message": "API cache expired.", "status_code": 404}
            return {"message": "API cache retrieved successfully.", "status_code": 200, "cache_value": cache.cache_value}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to retrieve API cache", cache_key=cache_key, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to retrieve API cache: {e}")
