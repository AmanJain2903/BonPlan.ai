# database/models/tripItinerariesTable.py

"""
This file contains the models for the trip itineraries table.
"""

from sqlalchemy import Column, Index, String, DateTime, Boolean, Enum, Integer, ForeignKey, Float, text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.database.database import Base
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableList
import uuid
import enum

class TripItineraryStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    GENERATED = "generated"

class TripItinerary(Base):
    __tablename__ = "trip_itineraries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String, nullable=True)
    origin = Column(String, nullable=True)
    destinations = Column(ARRAY(String), nullable=False, default=[])
    start_date = Column(JSONB, nullable=True)
    end_date = Column(JSONB, nullable=True)

    cost = Column(Float, nullable=True)
    days = Column(Integer, nullable=True)

    events = Column(MutableList.as_mutable(JSONB), nullable=False, default=[])
    smart_anchors = Column(MutableList.as_mutable(JSONB), nullable=False, server_default=text("'[]'"))

    tips = Column(ARRAY(String), nullable=False, default=[])

    status = Column(Enum(TripItineraryStatus), nullable=False, default=TripItineraryStatus.PENDING)

    # Tracks current position in the edit snapshot stack (0 = original generation).
    # /revert and /ahead move this cursor and restore events from the snapshots table.
    snapshot_cursor = Column(Integer, nullable=False, server_default=text("0"))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trip = relationship("Trip", back_populates="itineraries", lazy="selectin")