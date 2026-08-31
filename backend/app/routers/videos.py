"""Video project endpoints: upload/create, list, retrieve, delete, (re)process, transcript.

All endpoints require an authenticated user and are scoped to that user's
own video projects — a project owned by another user resolves to a 404
(NotFoundError) rather than a 403, so ownership is never leaked.

Video processing (transcription + highlight scoring) is CPU/IO-heavy and
can take a long time for long videos, so it is never run synchronously
inside a request handler. `POST /videos` and `POST /videos/{id}/process`
both schedule `run_process_video_project()` via `app.services.task_queue`,
which enqueues onto Redis in production (see task_queue.py) or falls back
to FastAPI's `BackgroundTasks` locally, running after the response has
been sent.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.rate_limit import rate_limit_video_submit
from app.database import SessionLocal
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError, ValidationAppError
from app.models.clip import ClipCaptionStyle, ClipFraming
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.models.video_project import (
    ClipLength,
    SourceType,
    VideoProject,
    VideoProjectStatus,
)
from app.schemas.video import (
    PaginatedVideoProjects,
    TranscriptSegmentResponse,
    VideoProjectResponse,
)
from app.services import storage, task_queue
from app.services.highlight_detection import detect_highlights
from app.services.transcription import TranscriptionError, transcribe_video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["videos"])


def _get_owned_project(db: Session, project_id: int, user: User) -> VideoProject:
    """Fetch a VideoProject by id, scoped to `user`, or raise NotFoundError."""

    project = (
        db.query(VideoProject)
        .filter(VideoProject.id == project_id, VideoProject.user_id == user.id)
        .first()
    )
    if project is None:
        raise NotFoundError("Video project")
    return project


async def process_video_project(project_id: int) -> None:
    """Background pipeline: transcribe a video project and score highlights.

    Invoked via `app.services.task_queue` (from the create and re-process
    endpoints) -- a real Redis-backed job in production, or FastAPI's
    BackgroundTasks locally -- so it runs outside the request/response
    cycle and opens its own DB session rather than reusing a request-scoped
    one.

    Status transitions: transcribing -> analyzing -> ready. On any
    exception, the project is marked status=failed with error_message set
    to a human-readable summary of the failure, and the exception is
    swallowed here (a background job must never raise into its runner).
    """

    db: Session = SessionLocal()
    try:
        project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
        if project is None:
            logger.error("process_video_project: project %s not found", project_id)
            return

        try:
            file_path = str(storage.get_file_path(project.source_file_path)) if project.source_file_path else None
            if not file_path or not Path(file_path).exists():
                if project.source_type == SourceType.url and project.source_url:
                    project.status = VideoProjectStatus.downloading
                    project.error_message = None
                    db.commit()
                    project.source_file_path = await storage.download_from_url(
                        project.source_url, "videos"
                    )
                    db.commit()
                    file_path = str(storage.get_file_path(project.source_file_path))
                else:
                    raise TranscriptionError(
                        "No source file available to transcribe for this project"
                    )

            project.status = VideoProjectStatus.transcribing
            project.error_message = None
            db.commit()

            file_path = str(storage.get_file_path(project.source_file_path))
            raw_segments = await transcribe_video(file_path)

            # Clear any previous transcript (e.g. this is a re-process run).
            db.query(TranscriptSegment).filter(
                TranscriptSegment.video_project_id == project.id
            ).delete()
            segments = [
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=seg["start_time"],
                    end_time=seg["end_time"],
                    text=seg["text"],
                )
                for seg in raw_segments
            ]
            db.add_all(segments)
            db.flush()

            project.status = VideoProjectStatus.analyzing
            if segments:
                project.duration_seconds = max(seg.end_time for seg in segments)
            db.commit()

            detect_highlights(segments)
            db.commit()

            project.status = VideoProjectStatus.ready
            db.commit()
        except Exception as exc:
            logger.error(
                "process_video_project failed for project %s: %s",
                project_id,
                exc,
                exc_info=exc,
            )
            db.rollback()
            project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
            if project is not None:
                project.status = VideoProjectStatus.failed
                project.error_message = str(exc)[:2000]
                db.commit()
    finally:
        db.close()


def run_process_video_project(project_id: int) -> None:
    """Sync entrypoint for `process_video_project`, for use as a queueable
    job. RQ workers (and, for that matter, Starlette's BackgroundTasks
    running a sync callable) call jobs as plain functions, not coroutines
    -- this just drives the async pipeline via its own event loop.
    """

    asyncio.run(process_video_project(project_id))


@router.post("", response_model=VideoProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_video_project(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    source_type: SourceType = Form(...),
    source_url: str | None = Form(default=None),
    target_clip_length: ClipLength = Form(default=ClipLength.auto),
    framing_mode: ClipFraming = Form(default=ClipFraming.speaker_focus),
    caption_style: ClipCaptionStyle = Form(default=ClipCaptionStyle.hormozi),
    auto_broll: bool = Form(default=True),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VideoProject:
    """Create a video project and kick off background processing.

    Accepts multipart/form-data with `title`, `source_type` ("upload" or
    "url"), and either a `file` part (required when source_type="upload")
    or a `source_url` form field (required when source_type="url").

    The remaining fields are what the submit form's options write, and they
    are what makes the generated shorts come out as asked:
    `target_clip_length` decides how long the clips are cut,
    `framing_mode` and `caption_style` become every generated clip's own
    settings, and `auto_broll` decides whether B-roll is sourced for them.
    All four have defaults, so a bare submission still works.
    """

    rate_limit_video_submit(user.id)

    if source_type == SourceType.url and not source_url:
        raise ValidationAppError("source_url is required when source_type is 'url'")
    if source_type == SourceType.upload and file is None:
        raise ValidationAppError("file is required when source_type is 'upload'")

    project = VideoProject(
        user_id=user.id,
        title=title,
        source_type=source_type,
        source_url=source_url if source_type == SourceType.url else None,
        status=VideoProjectStatus.pending,
        target_clip_length=target_clip_length,
        framing_mode=framing_mode,
        caption_style=caption_style,
        auto_broll=auto_broll,
    )

    if file is not None:
        relative_path = await storage.save_upload(file, "videos")
        project.source_file_path = relative_path

    db.add(project)
    db.commit()
    db.refresh(project)

    task_queue.enqueue(background_tasks, run_process_video_project, project.id)
    return project


@router.get("", response_model=PaginatedVideoProjects)
async def list_video_projects(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaginatedVideoProjects:
    """List the current user's video projects, newest first, paginated."""

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    base_query = db.query(VideoProject).filter(VideoProject.user_id == user.id)
    total = base_query.with_entities(func.count(VideoProject.id)).scalar() or 0
    items = (
        base_query.order_by(VideoProject.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # pydantic's from_attributes on VideoProjectResponse converts each ORM item here.
    return PaginatedVideoProjects(  # type: ignore[arg-type]
        items=items, total=total, page=page, page_size=page_size
    )


@router.get("/{project_id}", response_model=VideoProjectResponse)
async def get_video_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VideoProject:
    """Get a single video project owned by the current user (404 otherwise)."""

    return _get_owned_project(db, project_id, user)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Delete a video project (and its transcript segments / clips via cascade)."""

    project = _get_owned_project(db, project_id, user)
    db.delete(project)
    db.commit()


@router.post("/{project_id}/process", response_model=VideoProjectResponse)
async def reprocess_video_project(
    project_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VideoProject:
    """Re-trigger the transcription/highlight pipeline for an existing project."""

    project = _get_owned_project(db, project_id, user)
    project.status = VideoProjectStatus.pending
    project.error_message = None
    if project.source_type == SourceType.url:
        project.source_file_path = None
    db.commit()
    db.refresh(project)

    task_queue.enqueue(background_tasks, run_process_video_project, project.id)
    return project


@router.get("/{project_id}/transcript", response_model=list[TranscriptSegmentResponse])
async def get_video_transcript(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TranscriptSegment]:
    """List transcript segments for a project, ordered by start_time."""

    _get_owned_project(db, project_id, user)  # ownership check / 404
    return (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_project_id == project_id)
        .order_by(TranscriptSegment.start_time.asc())
        .all()
    )
