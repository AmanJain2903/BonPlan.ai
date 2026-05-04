# backend/app/services/trip_lifecycle.py

import asyncio
from datetime import datetime, timezone

from sqlalchemy import BigInteger, cast, delete, update
from sqlalchemy.dialects.postgresql import JSONB

from app.database.database import Session
from app.database.models.tripsTable import PlanStatus, Trip
from app.logging import get_app_logger

logger = get_app_logger("trip_lifecycle")

_INTERVAL_SECONDS = 60


def _now_utc_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def run_trip_lifecycle_update() -> None:
    now_ts = _now_utc_ts()
    try:
        async with Session() as db:
            # start_date passed: delete DRAFTs (DB cascade removes members/itineraries)
            deleted = await db.execute(
                delete(Trip).where(
                    cast(Trip.start_date["utcTimestamp"].astext, BigInteger) <= now_ts,
                    Trip.status == PlanStatus.DRAFT,
                )
            )

            # start_date passed: GENERATED → CURRENT
            activated = await db.execute(
                update(Trip)
                .where(
                    cast(Trip.start_date["utcTimestamp"].astext, BigInteger) <= now_ts,
                    Trip.status == PlanStatus.GENERATED,
                )
                .values(status=PlanStatus.CURRENT)
            )

            # end_date passed: active trips → COMPLETED
            completed = await db.execute(
                update(Trip)
                .where(
                    cast(Trip.end_date["utcTimestamp"].astext, BigInteger) <= now_ts,
                    Trip.status == PlanStatus.CURRENT,
                )
                .values(status=PlanStatus.COMPLETED)
            )

            await db.commit()

        d = deleted.rowcount
        a = activated.rowcount
        c = completed.rowcount
        if d or a or c:
            logger.info(
                "Trip lifecycle update",
                drafts_deleted=d,
                activated_current=a,
                completed=c,
            )
    except Exception:
        logger.exception("Trip lifecycle update failed")


async def trip_lifecycle_task() -> None:
    logger.info("Trip lifecycle task started")
    while True:
        await run_trip_lifecycle_update()
        await asyncio.sleep(_INTERVAL_SECONDS)
