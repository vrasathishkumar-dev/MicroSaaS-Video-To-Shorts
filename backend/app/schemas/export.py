"""Pydantic schemas for the Export & Publish module."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.models.clip import ClipStatus


class ExportStatusResponse(BaseModel):
    """Current render/export status of a clip.

    Returned by both POST /clips/{id}/export (immediately, status=rendering)
    and GET /clips/{id}/export/status (polled by the frontend until the
    status settles to `ready` or `failed`).
    """

    clip_id: int
    status: ClipStatus
    video_file_path: str | None = None

    model_config = ConfigDict(from_attributes=True)
