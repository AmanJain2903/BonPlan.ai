# backend/app/services/rate_limiter/usage_cleanup.py

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, delete

from app.core.config import settings
from app.database.database import Session
from app.database.models.rateLimitConfigs import RateLimitConfigs, Period
from app.database.models.rateLimitUsage import RateLimitUsage

logger = logging.getLogger(__name__)

def _get_threshold_bucket(period: Period, tz: ZoneInfo) -> str:
    """
    Returns the threshold bucket string for a given period.
    Buckets lexicographically smaller than this threshold are considered old and can be deleted.
    """
    now = datetime.now(tz)
    
    if period == Period.DAILY:
        # Delete older than 1 week (7 days)
        threshold_date = now - timedelta(days=7)
        return threshold_date.strftime("%Y%m%d")
        
    elif period == Period.WEEKLY:
        # Delete older than 1 month (roughly 4 weeks / 30 days)
        threshold_date = now - timedelta(days=30)
        iso_year, iso_week, _ = threshold_date.isocalendar()
        return f"{iso_year}W{iso_week:02d}"
        
    elif period == Period.MONTHLY:
        # Delete older than 1 year (365 days)
        threshold_date = now - timedelta(days=365)
        return threshold_date.strftime("%Y%m")
        
    elif period == Period.YEARLY:
        # Delete older than 2 years
        threshold_date = now.replace(year=now.year - 2)
        return threshold_date.strftime("%Y")
        
    raise ValueError(f"Unknown period: {period}")

async def cleanup_old_usage():
    """
    Cleans up old rate limit usage entries from the database based on the 'one level up' rule.
    """
    tz = ZoneInfo(settings.RATE_LIMITER_RESET_TZ)
    
    deleted_count = 0
    try:
        async with Session() as db:
            # We must process each period type separately to compare with its specific threshold
            for period in Period:
                threshold_bucket = _get_threshold_bucket(period, tz)
                
                # Find all usage rows for this period whose bucket is strictly less than the threshold.
                # Since buckets are lexicographically sortable, this works perfectly.
                stmt = delete(RateLimitUsage).where(
                    RateLimitUsage.sku_id.in_(
                        select(RateLimitConfigs.id).where(RateLimitConfigs.period == period)
                    )
                ).where(RateLimitUsage.period_bucket < threshold_bucket)
                
                result = await db.execute(stmt)
                deleted_count += result.rowcount
                
            await db.commit()
            
        if deleted_count > 0:
            logger.info("Usage cleanup deleted %d old entries.", deleted_count)
            
    except Exception as e:
        logger.error("Usage cleanup failed: %s", e)

async def usage_cleanup_task():
    """
    Background task that runs the cleanup periodically.
    Runs once on startup, then every 24 hours.
    """
    while True:
        await cleanup_old_usage()
        # Sleep for 24 hours
        await asyncio.sleep(24 * 60 * 60)
