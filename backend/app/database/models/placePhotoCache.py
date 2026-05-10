# database/models/placePhotoCache.py

"""
Model for caching Google Places photo binaries server-side.

Local dev: raw bytes in image_data column.
Prod: image uploaded to Cloudflare R2, r2_url stored here.
Entries auto-expire after 30 days per Google's ToS allowance.
"""

from sqlalchemy import Column, Integer, String, LargeBinary, DateTime
from app.database.database import Base
from sqlalchemy.sql import func


class PlacePhotoCache(Base):
    __tablename__ = "place_photo_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_name = Column(String, nullable=False, unique=True, index=True)
    # Local dev only — raw image binary (JPEG/PNG/WebP); None in prod
    image_data = Column(LargeBinary, nullable=True)
    # Prod only — Cloudflare R2 URL; None in local dev
    r2_url = Column(String, nullable=True)
    content_type = Column(String, nullable=False, default="image/jpeg")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
