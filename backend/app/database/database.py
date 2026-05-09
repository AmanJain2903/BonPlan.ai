# backend/app/database/database.py

"""
Async database connection and session management.
"""

from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
import uuid

from app.core.config import settings

engine_kwargs = {
    "echo": False,
    "future": True
}

if settings.LOCAL_DEVELOPMENT:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 5,
        "max_overflow": 10,
    })
else:
    engine_kwargs.update({
        "poolclass": NullPool,
        "connect_args": {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
    }
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

Session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()
