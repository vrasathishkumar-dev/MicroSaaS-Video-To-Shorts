"""Dashboard summary endpoints.

Owned by BACKEND-AGENT. Read-only aggregation over VideoProject and Clip
rows belonging to the current user; does not modify any other module's
models or routers.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.models.video_project import VideoProject, VideoProjectStatus
from app.schemas.dashboard import DashboardStatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardStatsResponse:
    """Return aggregate video/clip statistics for the current user.

    All counts and averages are computed via SQL aggregation
    (func.count/func.avg), scoped to the authenticated user, rather than
    loading and iterating over full result sets in Python.
    """

    user_id = current_user.id

    # total_videos: single count aggregation.
    total_videos: int = (
        db.query(func.count(VideoProject.id))
        .filter(VideoProject.user_id == user_id)
        .scalar()
        or 0
    )

    # videos_by_status: grouped count aggregation.
    status_rows = (
        db.query(VideoProject.status, func.count(VideoProject.id))
        .filter(VideoProject.user_id == user_id)
        .group_by(VideoProject.status)
        .all()
    )
    videos_by_status: dict[str, int] = {
        (status.value if hasattr(status, "value") else status): count
        for status, count in status_rows
    }

    # total_clips: single count aggregation.
    total_clips: int = (
        db.query(func.count(Clip.id)).filter(Clip.user_id == user_id).scalar() or 0
    )

    # clips_ready: filtered count aggregation.
    clips_ready: int = (
        db.query(func.count(Clip.id))
        .filter(Clip.user_id == user_id, Clip.status == ClipStatus.ready)
        .scalar()
        or 0
    )

    # avg_processing_time_seconds: average of (updated_at - created_at), in
    # seconds, for the user's VideoProjects that have finished processing
    # (status=ready). Computed server-side via extract('epoch', ...) on the
    # timestamp difference so Postgres does the averaging, not Python.
    # None when the user has no ready video projects.
    avg_seconds = (
        db.query(
            func.avg(
                func.extract("epoch", VideoProject.updated_at)
                - func.extract("epoch", VideoProject.created_at)
            )
        )
        .filter(
            VideoProject.user_id == user_id,
            VideoProject.status == VideoProjectStatus.ready,
        )
        .scalar()
    )
    avg_processing_time_seconds: float | None = (
        float(avg_seconds) if avg_seconds is not None else None
    )

    # storage_used_bytes: best-effort disk usage.
    #
    # Approach: pull only the path columns (not full rows) for the user's
    # VideoProject.source_file_path and Clip.video_file_path, then sum
    # os.path.getsize() for whichever paths exist on local disk. This is a
    # best-effort estimate only:
    #   - it does not account for remote/object storage (S3, etc.) — only
    #     local filesystem paths are inspected;
    #   - null paths (not yet uploaded/rendered) and paths that no longer
    #     exist on disk (moved, purged, remote-only) are silently skipped;
    #   - any OS-level error reading a given path (permissions, races) is
    #     swallowed for that path so one bad path doesn't fail the whole
    #     stats request.
    # If neither path column yields any readable file, this returns 0.
    storage_used_bytes = 0
    source_paths = (
        db.query(VideoProject.source_file_path)
        .filter(VideoProject.user_id == user_id)
        .all()
    )
    clip_paths = (
        db.query(Clip.video_file_path).filter(Clip.user_id == user_id).all()
    )
    for (path,) in [*source_paths, *clip_paths]:
        if not path:
            continue
        try:
            storage_used_bytes += os.path.getsize(path)
        except OSError:
            # Missing/inaccessible file — skip silently, best-effort only.
            continue

    return DashboardStatsResponse(
        total_videos=total_videos,
        videos_by_status=videos_by_status,
        total_clips=total_clips,
        clips_ready=clips_ready,
        avg_processing_time_seconds=avg_processing_time_seconds,
        storage_used_bytes=storage_used_bytes,
    )
