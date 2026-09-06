"""BrollAsset model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.clip import Clip


class BrollSource(str, enum.Enum):
    """Stock footage provider a B-roll asset was sourced from."""

    pexels = "pexels"
    pixabay = "pixabay"


class BrollAsset(Base):
    """A piece of B-roll footage/image inserted into a clip."""

    __tablename__ = "broll_assets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    clip_id: Mapped[int] = mapped_column(
        ForeignKey("clips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[BrollSource] = mapped_column(
        Enum(BrollSource, name="broll_source"), nullable=False
    )
    source_asset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    position_start: Mapped[float] = mapped_column(Float, nullable=False)
    position_end: Mapped[float] = mapped_column(Float, nullable=False)
    # True only for rows `auto_source_broll` created. Lets a re-click of
    # "Auto-insert B-roll" replace its own previous batch instead of piling
    # duplicates on top of it, without touching anything the user added
    # manually via search -- those are never marked auto-generated.
    auto_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    clip: Mapped[Clip] = relationship("Clip", back_populates="broll_assets")

    def __repr__(self) -> str:
        return f"<BrollAsset id={self.id} clip_id={self.clip_id} source={self.source}>"
