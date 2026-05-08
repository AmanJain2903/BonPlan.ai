# database/models/emailSubscriptionsTable.py

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database.database import Base


class EmailSubscription(Base):
    __tablename__ = "email_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_email_subscriptions_user_category"),
        Index("ix_email_subscriptions_token", "token", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    token = Column(String, nullable=False)
    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
