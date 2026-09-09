"""VideoProject model."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.clip import ClipCaptionStyle, ClipFraming

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.transcript_segment import TranscriptSegment
    from app.models.user import User


class SourceType(str, enum.Enum):
    """Where the source video came from."""

    upload = "upload"
    url = "url"
    text = "text"  # AI-generated from a title + description prompt


class VideoProjectStatus(str, enum.Enum):
    """Processing pipeline status of a video project."""

    pending = "pending"
    downloading = "downloading"
    transcribing = "transcribing"
    analyzing = "analyzing"
    generating = "generating"  # AI text-to-video pipeline in progress
    ready = "ready"
    failed = "failed"


class ClipLength(str, enum.Enum):
    """How long the shorts cut from this video should aim to be.

    Chosen at submission, because it decides how the highlights are cut --
    not something that can be applied to clips after the fact.
    """

    auto = "auto"
    fast = "fast"
    in_depth = "in_depth"


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

    # Text-to-shorts generation metadata (populated when source_type=text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    shorts_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


    # What the submitter asked for. `target_clip_length` shapes how the
    # highlights are cut; the rest are the defaults every clip generated
    # from this video is born with, so the shorts come out as ordered
    # without anyone opening the editor. All still editable per clip
    # afterwards -- these are starting points, not locks.
    target_clip_length: Mapped[ClipLength] = mapped_column(
        Enum(ClipLength, name="clip_length"),
        default=ClipLength.auto,
        server_default=ClipLength.auto.value,
        nullable=False,
    )
    framing_mode: Mapped[ClipFraming] = mapped_column(
        Enum(ClipFraming, name="clip_framing"),
        default=ClipFraming.speaker_focus,
        server_default=ClipFraming.speaker_focus.value,
        nullable=False,
    )
    caption_style: Mapped[ClipCaptionStyle] = mapped_column(
        Enum(ClipCaptionStyle, name="clip_caption_style"),
        default=ClipCaptionStyle.hormozi,
        server_default=ClipCaptionStyle.hormozi.value,
        nullable=False,
    )
    auto_broll: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

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
