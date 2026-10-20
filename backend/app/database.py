"""SQLAlchemy engine/session setup and the FastAPI `get_db` dependency."""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.base import Base

logger = logging.getLogger(__name__)

_raw_url = settings.DATABASE_URL
if _raw_url.startswith("postgresql://"):
    DATABASE_URL: str = _raw_url.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    DATABASE_URL: str = _raw_url

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

__all__ = ["DATABASE_URL", "Base", "SessionLocal", "engine", "get_db"]


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
