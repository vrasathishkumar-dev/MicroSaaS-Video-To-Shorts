"""Pydantic schemas for video projects and transcript segments."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.clip import ClipCaptionStyle, ClipFraming
from app.models.video_project import ClipLength, SourceType, VideoProjectStatus


class VideoProjectCreate(BaseModel):
    """Logical shape of a "create video project" request.

    In practice the API endpoint accepts these fields as multipart form
    fields (alongside an optional `file` upload part) rather than a raw
    JSON body, since a file upload and JSON body cannot coexist in the same
    request — but this schema documents/validates the same field shape and
    is reused for OpenAPI docs.
    """

    title: str = Field(min_length=1, max_length=255)
    source_type: SourceType
    source_url: str | None = Field(default=None, max_length=2048)

    # How the shorts should come out. `target_clip_length` shapes how the
    # highlights are cut; the others are inherited by every clip generated
    # from this video and stay editable per clip afterwards.
    target_clip_length: ClipLength = ClipLength.auto
    framing_mode: ClipFraming = ClipFraming.speaker_focus
    caption_style: ClipCaptionStyle = ClipCaptionStyle.hormozi
    auto_broll: bool = True

    @model_validator(mode="after")
    def _validate_source_url_required_for_url_type(self) -> VideoProjectCreate:
        if self.source_type == SourceType.url and not self.source_url:
            raise ValueError("source_url is required when source_type is 'url'")
        return self


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_project_id: int
    start_time: float
    end_time: float
    text: str
    is_highlight: bool
    highlight_score: float | None = None


class VideoProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    source_type: SourceType
    source_url: str | None = None
    source_file_path: str | None = None
    status: VideoProjectStatus
    duration_seconds: float | None = None
    error_message: str | None = None
    target_clip_length: ClipLength
    framing_mode: ClipFraming
    caption_style: ClipCaptionStyle
    auto_broll: bool
    created_at: datetime
    updated_at: datetime


class PaginatedVideoProjects(BaseModel):
    """Envelope matching the frontend's PaginatedResponse<T> type."""

    items: list[VideoProjectResponse]
    total: int
    page: int
    page_size: int
