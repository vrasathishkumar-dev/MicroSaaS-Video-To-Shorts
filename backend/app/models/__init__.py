"""SQLAlchemy models for VideoToShorts.

Import all models here so that:
  - `Base.metadata` is fully populated for Alembic autogenerate.
  - Other modules can do `from app.models import User, Clip, ...`.
"""

from __future__ import annotations

from app.models.base import Base, TimestampMixin
from app.models.broll_asset import BrollAsset, BrollSource
from app.models.clip import Clip, ClipStatus
from app.models.refresh_token import RefreshToken
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus

__all__ = [
    "Base",
    "BrollAsset",
    "BrollSource",
    "Clip",
    "ClipStatus",
    "RefreshToken",
    "SourceType",
    "TimestampMixin",
    "TranscriptSegment",
    "User",
    "VideoProject",
    "VideoProjectStatus",
]
