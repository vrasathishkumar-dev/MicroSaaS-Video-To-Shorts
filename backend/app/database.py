"""SQLAlchemy engine/session setup and the FastAPI `get_db` dependency."""

from __future__ import annotations

import logging
import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.base import Base

logger = logging.getLogger(__name__)

DATABASE_URL: str = settings.DATABASE_URL

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
