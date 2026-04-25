# database/models/rateLimitConfigs.py

"""
Model for caching rate limit configurations for the API.
"""

from sqlalchemy import Column, Integer, String, Enum, DateTime
import enum
from app.database.database import Base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Period(enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class Scope(enum.Enum):
    USER = "user"
    GLOBAL = "global"

class RateLimitConfigs(Base):
    __tablename__ = "rate_limit_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True, unique=True)
    sku = Column(String, nullable=False, unique=True, index=True)
    service = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    provider = Column(String, nullable=False)
    limit = Column(Integer, nullable=False, default=-1)
    period = Column(Enum(Period), nullable=False, default=Period.MONTHLY)
    scope = Column(Enum(Scope), nullable=False, default=Scope.GLOBAL)
    # ─── Per-SKU reset anchor (interpreted in RATE_LIMITER_RESET_TZ) ────────
    # The exact wall-clock moment a period flips. Interpretation per period:
    #   DAILY   — reset_hour:reset_minute every day
    #   WEEKLY  — every reset_day (1=Mon … 7=Sun) at reset_hour:reset_minute
    #   MONTHLY — every reset_day-of-month at reset_hour:reset_minute
    #             (clamped to last day of months that don't have it)
    #   YEARLY  — every reset_month/reset_day at reset_hour:reset_minute
    # Defaults map to the previous global behavior: midnight on the 1st.
    reset_minute = Column(Integer, nullable=False, default=0, server_default='0')
    reset_hour = Column(Integer, nullable=False, default=0, server_default='0')
    reset_day = Column(Integer, nullable=False, default=1, server_default='1')
    reset_month = Column(Integer, nullable=False, default=1, server_default='1')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    usage = relationship("RateLimitUsage", back_populates="config", cascade="all, delete-orphan", lazy="selectin")

