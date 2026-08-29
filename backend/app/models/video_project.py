"""VideoProject model."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.transcript_segment import TranscriptSegment
    from app.models.user import User


class SourceType(str, enum.Enum):
    """Where the source video came from."""

    upload = "upload"
    url = "url"


class VideoProjectStatus(str, enum.Enum):
    """Processing pipeline status of a video project."""

    pending = "pending"
    downloading = "downloading"
    transcribing = "transcribing"
    analyzing = "analyzing"
    ready = "ready"
    failed = "failed"


class VideoProject(Base, TimestampMixin):
    """A long-form video submitted for processing into short clips."""

    __tablename__ = "video_projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type"), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[VideoProjectStatus] = mapped_column(
        Enum(VideoProjectStatus, name="video_project_status"),
        default=VideoProjectStatus.pending,
        nullable=False,
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="video_projects")
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        "TranscriptSegment",
        back_populates="video_project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    clips: Mapped[list[Clip]] = relationship(
        "Clip",
        back_populates="video_project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<VideoProject id={self.id} title={self.title!r} status={self.status}>"
