# database/models/usersTable.py

"""
This file contains the models for the users table.
"""

from sqlalchemy import Column, Index, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database.database import Base
from sqlalchemy.sql import func
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    is_admin = Column(Boolean, nullable=False, default=False, server_default='false')
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(JSONB, nullable=True)
    password_hash = Column(String, nullable=True)
    auth_provider = Column(String, nullable=False, default='local')
    is_verified = Column(Boolean, nullable=False, default=False)
    is_new_user = Column(Boolean, nullable=False, default=True)
    preferences = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            'ix_users_phone_unique',
            phone['country_code'].astext,
            phone['number'].astext,
            unique=True,
        ),
    )

    trip_memberships = relationship(
        "TripMember",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="TripMember.user_id",
        lazy="selectin",
    )
    owned_trips = relationship("Trip", back_populates="owner", cascade="all, delete-orphan", lazy="selectin")
    collab_qa = relationship("TripCollabQA", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
