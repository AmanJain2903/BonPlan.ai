# database/models/apiCache.py

"""
This file contains the models for the API cache table.
"""

from sqlalchemy import Column, Index, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from app.database.database import Base
from sqlalchemy.sql import func
from datetime import timedelta

class ApiCache(Base):
    __tablename__ = "api_cache"

    cache_key = Column(String, nullable=False, index=True, unique=True, primary_key=True)
    cache_value = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
