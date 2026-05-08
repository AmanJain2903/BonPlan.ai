# database/models/rateLimitAlertEventsTable.py

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.database import Base


class RateLimitAlertEvent(Base):
    __tablename__ = "rate_limit_alert_events"
    __table_args__ = (
        UniqueConstraint(
            "sku_id",
            "period_bucket",
            "usage_owner",
            "threshold_percent",
            name="uq_rate_limit_alert_event",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    sku_id = Column(UUID(as_uuid=True), ForeignKey("rate_limit_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String, nullable=False, index=True)
    period_bucket = Column(String, nullable=False, index=True)
    usage_owner = Column(String, nullable=False, default="global", server_default="global")
    threshold_percent = Column(Integer, nullable=False)
    usage = Column(Integer, nullable=False)
    limit = Column(Integer, nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
