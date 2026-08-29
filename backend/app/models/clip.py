"""Clip model."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.broll_asset import BrollAsset
    from app.models.user import User
    from app.models.video_project import VideoProject


class ClipStatus(str, enum.Enum):
    """Render/lifecycle status of a clip."""

    draft = "draft"
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


class Clip(Base, TimestampMixin):
    """A short, vertical clip generated from a VideoProject."""

    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    video_project_id: Mapped[int] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ClipStatus] = mapped_column(
        Enum(ClipStatus, name="clip_status"), default=ClipStatus.draft, nullable=False
    )
    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    video_project: Mapped[VideoProject] = relationship("VideoProject", back_populates="clips")
    user: Mapped[User] = relationship("User", back_populates="clips")
    broll_assets: Mapped[list[BrollAsset]] = relationship(
        "BrollAsset",
        back_populates="clip",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Clip id={self.id} video_project_id={self.video_project_id} status={self.status}>"
