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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    usage = relationship("RateLimitUsage", back_populates="config", cascade="all, delete-orphan", lazy="selectin")

