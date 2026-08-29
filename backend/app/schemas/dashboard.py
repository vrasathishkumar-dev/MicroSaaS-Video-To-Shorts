"""Pydantic schemas for the Dashboard resource."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DashboardStatsResponse(BaseModel):
    """Aggregate usage/processing statistics for the current user.

    All figures are scoped to the authenticated user only.
    """

    total_videos: int
    videos_by_status: dict[str, int]
    total_clips: int
    clips_ready: int
    avg_processing_time_seconds: float | None
    storage_used_bytes: int | None

    model_config = ConfigDict(from_attributes=True)
