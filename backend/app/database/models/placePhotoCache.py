# database/models/placePhotoCache.py

"""
Model for caching Google Places photo binaries server-side.

Stores the raw image bytes so the frontend never hits Google directly,
preventing repeated billing for the same photo. Entries auto-expire
after 30 days per Google's ToS allowance.
"""

from sqlalchemy import Column, Integer, String, LargeBinary, DateTime
from app.database.database import Base
from sqlalchemy.sql import func


class PlacePhotoCache(Base):
    __tablename__ = "place_photo_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # The Google resource name, e.g. "places/ChIJ.../photos/abc123"
    resource_name = Column(String, nullable=False, unique=True, index=True)
    # Raw image binary (JPEG/PNG/WebP)
    image_data = Column(LargeBinary, nullable=False)
    # MIME type returned by Google
    content_type = Column(String, nullable=False, default="image/jpeg")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
