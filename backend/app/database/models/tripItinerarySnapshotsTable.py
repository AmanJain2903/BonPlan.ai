# database/models/tripItinerarySnapshotsTable.py

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base
import uuid


class TripItinerarySnapshot(Base):
    __tablename__ = "trip_itinerary_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)

    version_index = Column(Integer, nullable=False)
    events = Column(JSONB, nullable=False, default=list)
    cost = Column(Float, nullable=True)
    title = Column(String, nullable=True)
    tips = Column(ARRAY(String), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trip = relationship("Trip", back_populates="itinerary_snapshots", lazy="selectin")
