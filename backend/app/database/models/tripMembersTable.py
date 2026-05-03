# database/models/tripsMembersTable.py

"""
This file contains the models for the trips members table.
"""

from sqlalchemy import Column, Index, String, DateTime, Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.database.database import Base
from sqlalchemy.sql import func
import uuid
import enum

class TripRole(str, enum.Enum):
    OWNER = "owner"
    GROUP_MEMBER = "group_member"
    SHARED_EDITOR = "shared_editor"
    SHARED_VIEWER = "shared_viewer"

class TripInvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"

class TripMember(Base):
    __tablename__ = "trip_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    invited_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    invited_email = Column(String, nullable=True, index=True)

    role = Column(Enum(TripRole), nullable=False)
    invitation_status = Column(String, nullable=False, default=TripInvitationStatus.ACCEPTED.value)
    invitation_token_hash = Column(String, nullable=True, unique=True, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    trip_preferences = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('trip_id', 'user_id', name='uix_trip_user'),
        UniqueConstraint('trip_id', 'invited_email', name='uix_trip_invited_email'),
    )

    trip = relationship("Trip", back_populates="members", lazy="selectin")
    user = relationship("User", back_populates="trip_memberships", foreign_keys=[user_id], lazy="selectin")
