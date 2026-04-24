# database/models/rateLimitUsage.py

"""
Model for tracking rate limit usage for the API.
"""

from sqlalchemy import Column, Integer, UniqueConstraint
from app.database.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
import uuid
from sqlalchemy.dialects.postgresql import UUID

class RateLimitUsage(Base):
    __tablename__ = "rate_limit_usage"
    __table_args__ = (
        UniqueConstraint("sku_id", "user_id", name="uq_rate_limit_usage_sku_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True, unique=True)
    sku_id = Column(UUID(as_uuid=True), ForeignKey("rate_limit_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    usage = Column(Integer, nullable=False, default=0)

    config = relationship("RateLimitConfigs", back_populates="usage", lazy="selectin")
    user = relationship("User", back_populates="usage", lazy="selectin")
