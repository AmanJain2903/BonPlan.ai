# database/models/tripCollabQATable.py

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.sql import func
from app.database.database import Base
import uuid


class TripCollabQA(Base):
    __tablename__ = "trip_collab_qa"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False, index=True)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Each entry: {call_id, question, options, answer_type, skippable,
    #              answer, skipped, context}
    # context is "seed" for the collaboration_checkpoint question,
    # "day_N" for mid-day questions asked by the LLM.
    qa_pairs = Column(MutableList.as_mutable(JSONB), nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("trip_id", "user_id", name="uq_trip_collab_qa_trip_user"),
    )

    trip = relationship("Trip", back_populates="collab_qa", lazy="selectin")
    user = relationship("User", back_populates="collab_qa", lazy="selectin")
