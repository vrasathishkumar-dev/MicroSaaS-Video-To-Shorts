"""TranscriptSegment model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.video_project import VideoProject


class TranscriptSegment(Base):
    """A single transcribed segment of a video project, possibly flagged as a highlight."""

    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    video_project_id: Mapped[int] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_highlight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    highlight_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    video_project: Mapped[VideoProject] = relationship(
        "VideoProject", back_populates="transcript_segments"
    )

    def __repr__(self) -> str:
        return (
            f"<TranscriptSegment id={self.id} video_project_id={self.video_project_id} "
            f"start_time={self.start_time} end_time={self.end_time}>"
        )
