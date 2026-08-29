"""Export & Publish endpoints: render, poll status, download.

Owned by BACKEND-AGENT (Export & Publish module). Registered under the
`/clips` prefix so the final paths are /clips/{id}/export,
/clips/{id}/export/status, and /clips/{id}/download -- the Clip Library
module (app/routers/clips.py) owns /clips, /clips/{id}, and
/clips/{id}/reorder and does not define these sub-paths.

Ownership of a clip is checked directly against the Clip model here
(rather than importing the Clip Library module's service layer) to avoid
cross-module coupling, per the module's file-ownership boundaries.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_current_user_for_media, get_db
from app.exceptions import NotFoundError, ValidationAppError
from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.schemas.export import ExportStatusResponse
from app.services import task_queue
from app.services.storage import get_file_path
from app.services.video_render import render_clip

router = APIRouter(prefix="/clips", tags=["export"])

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _get_owned_clip(db: Session, clip_id: int, user_id: int) -> Clip:
    """Fetch a clip by id, scoped to the owning user.

    Raises:
        NotFoundError: no clip with that id exists, or it belongs to
            another user.
    """

    clip = db.query(Clip).filter(Clip.id == clip_id, Clip.user_id == user_id).first()
    if clip is None:
        raise NotFoundError("Clip")
    return clip


@router.post("/{clip_id}/export", response_model=ExportStatusResponse)
async def export_clip(
    clip_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExportStatusResponse:
    """Kick off rendering a clip into an exportable, downloadable MP4.

    Marks the clip `rendering` and schedules the actual ffmpeg work via
    app.services.task_queue (a real Redis-backed job in production, or
    BackgroundTasks locally) so this request returns immediately -- per
    CLAUDE.md, long video processing must never run synchronously in a
    request handler. Poll GET /clips/{id}/export/status for completion.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)
    clip.status = ClipStatus.rendering
    db.commit()
    db.refresh(clip)

    task_queue.enqueue(background_tasks, render_clip, clip.id)

    return ExportStatusResponse(
        clip_id=clip.id, status=clip.status, video_file_path=clip.video_file_path
    )


@router.get("/{clip_id}/export/status", response_model=ExportStatusResponse)
async def get_export_status(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExportStatusResponse:
    """Poll target for the current render status of a clip."""

    clip = _get_owned_clip(db, clip_id, current_user.id)
    return ExportStatusResponse(
        clip_id=clip.id, status=clip.status, video_file_path=clip.video_file_path
    )


@router.get("/{clip_id}/preview")
async def preview_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_for_media),
) -> FileResponse:
    """Stream a clip's video for inline `<video>` preview playback.

    Serves the rendered export once the clip is `ready`; otherwise streams
    the parent video project's full source file so drafts can be previewed
    (by seeking client-side to [start_time, end_time]) without waiting for
    an export to finish. Auth is via `?token=` -- see
    get_current_user_for_media for why.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)

    if clip.status == ClipStatus.ready and clip.video_file_path:
        path = Path(clip.video_file_path)
    else:
        source_path = clip.video_project.source_file_path if clip.video_project else None
        if not source_path:
            raise NotFoundError("Source video")
        path = get_file_path(source_path)

    if not path.is_file():
        raise NotFoundError("Preview video file")

    return FileResponse(path=path, media_type="video/mp4")


@router.get("/{clip_id}/download")
async def download_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Stream the rendered MP4 as an attachment, once export has completed.

    Raises:
        ValidationAppError: the clip hasn't finished rendering (or failed).
        NotFoundError: status says ready but the file is missing on disk.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)

    if clip.status != ClipStatus.ready or not clip.video_file_path:
        raise ValidationAppError("Clip export is not ready for download yet")

    path = Path(clip.video_file_path)
    if not path.is_file():
        raise NotFoundError("Exported video file")

    safe_title = _UNSAFE_FILENAME_CHARS.sub("-", clip.title).strip("-") or "clip"
    filename = f"{safe_title}-{clip.id}.mp4"

    return FileResponse(path=path, media_type="video/mp4", filename=filename)
