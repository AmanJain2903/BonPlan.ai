# database/models/tripsTable.py

"""
This file contains the models for the trips table.
"""

from sqlalchemy import Column, Index, String, DateTime, Boolean, Enum, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.database.database import Base
from sqlalchemy.sql import func
import uuid
import enum

class PlanningType(str, enum.Enum):
    SOLO = "solo"
    SQUAD = "squad"

class RoutingStyle(str, enum.Enum):
    SINGLE_HUB = "single-hub"
    MULTI_HOP = "multi-hop"

class PlanStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED = "generated"
    EDITING = "editing"
    CURRENT = "current"
    COMPLETED = "completed"

class Trip(Base):
    __tablename__ = "trips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    planning_type = Column(Enum(PlanningType), nullable=False)
    routing_style = Column(Enum(RoutingStyle), nullable=False)

    origin = Column(JSONB, nullable=False)
    destinations = Column(ARRAY(JSONB), nullable=False)
    start_date = Column(JSONB, nullable=False)
    end_date = Column(JSONB, nullable=False)
    pace = Column(String, nullable=False)
    budget = Column(String, nullable=False)

    adults = Column(Integer, nullable=False)
    children = Column(Integer, nullable=False)

    status = Column(Enum(PlanStatus), nullable=False, default=PlanStatus.DRAFT)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    members = relationship("TripMember", back_populates="trip", cascade="all, delete-orphan", lazy="selectin")
    itineraries = relationship("TripItinerary", back_populates="trip", cascade="all, delete-orphan", lazy="selectin")
    collab_qa = relationship("TripCollabQA", back_populates="trip", cascade="all, delete-orphan", lazy="selectin")
    itinerary_snapshots = relationship("TripItinerarySnapshot", back_populates="trip", cascade="all, delete-orphan", lazy="selectin")
    owner = relationship("User", back_populates="owned_trips", lazy="selectin")