"""Pydantic schemas for the Clip resource."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from app.models.clip import ClipCaptionStyle, ClipFraming, ClipStatus
from app.schemas.broll import BrollAssetResponse


class ClipResponse(BaseModel):
    """Full representation of a Clip returned to clients."""

    id: int
    video_project_id: int
    user_id: int
    title: str
    start_time: float
    end_time: float
    order_index: int
    status: ClipStatus
    caption_text: str | None
    framing_mode: ClipFraming
    caption_style: ClipCaptionStyle
    video_file_path: str | None
    thumbnail_path: str | None
    broll_assets: list[BrollAssetResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClipUpdateRequest(BaseModel):
    """Partial update payload for a Clip. All fields optional.

    `framing_mode` and `caption_style` are what the editor's framing toggle
    and caption picker write: the export reads them back, so choosing a
    look in the studio is what the rendered short actually gets.
    """

    title: str | None = Field(default=None, min_length=1, max_length=255)
    start_time: float | None = Field(default=None, ge=0)
    end_time: float | None = Field(default=None, ge=0)
    caption_text: str | None = None
    framing_mode: ClipFraming | None = None
    caption_style: ClipCaptionStyle | None = None


class ClipGenerateRequest(BaseModel):
    """Request body for generating clips from a video project's highlights."""

    video_project_id: int


class ClipReorderRequest(BaseModel):
    """Request body for reordering a clip among its siblings."""

    order_index: int = Field(ge=0)


class PaginatedClips(BaseModel):
    """Paginated envelope for a list of clips."""

    items: list[ClipResponse]
    total: int
    page: int
    page_size: int
