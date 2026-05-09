# database/models/rateLimitAlertSettingsTable.py

import uuid

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.database.database import Base


class RateLimitAlertSettings(Base):
    __tablename__ = "rate_limit_alert_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    key = Column(String, nullable=False, unique=True, default="global", server_default="global")
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    thresholds = Column(JSONB, nullable=False, default=lambda: [80, 90, 100], server_default="[80, 90, 100]")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
