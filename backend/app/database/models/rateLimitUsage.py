# database/models/rateLimitUsage.py

"""
Persistent counter mirror for the surgical rate limiter.

Why this exists:
- Redis is the hot path (atomic INCR via Lua, sub-ms reads), but it is
  ephemeral — a Redis restart or eviction would zero every counter and
  hand a fresh quota to whoever called next. For monthly SKUs that costs
  real money.

Schema notes:
- `period_bucket` is the same string the limiter uses in the Redis key
  (e.g. "202604" for monthly, "2026W17" for weekly).
"""

from sqlalchemy import Column, Integer, String, UniqueConstraint, Index
from app.database.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

# Sentinel UUID written into `user_id` for GLOBAL-scope rows so the unique
# constraint behaves the same way it does for USER-scope rows.
GLOBAL_USER_SENTINEL = uuid.UUID("00000000-0000-0000-0000-000000000000")


class RateLimitUsage(Base):
    __tablename__ = "rate_limit_usage"
    __table_args__ = (
        UniqueConstraint(
            "sku_id",
            "user_id",
            "period_bucket",
            name="uq_rate_limit_usage_sku_user_bucket",
        ),
        Index("ix_rate_limit_usage_bucket", "period_bucket"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True, unique=True)
    sku_id = Column(UUID(as_uuid=True), ForeignKey("rate_limit_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    sku = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    period_bucket = Column(String, nullable=False)
    usage = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    config = relationship("RateLimitConfigs", back_populates="usage", lazy="selectin")
