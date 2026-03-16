# backend/app/database/database.py

"""
Database connection and session management.
"""

from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Get a database session
def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()