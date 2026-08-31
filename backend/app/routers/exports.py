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

import logging
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_current_user, get_current_user_for_media, get_db
from app.exceptions import NotFoundError, ValidationAppError
from app.models.broll_asset import BrollAsset
from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.schemas.export import (
    CaptionFrame,
    ClipCaptionsResponse,
    ClipFramingResponse,
    ExportStatusResponse,
    SpeakerFocusWindow,
    SplitScreenSection,
)
from app.services import task_queue
from app.services.broll_sourcing import auto_source_broll
from app.services.caption_render import CAPTION_STYLES, caption_frames
from app.services.reframe import SpeakerWindow, compute_speaker_framing
from app.services.storage import get_file_path
from app.services.video_render import _caption_events, render_clip

logger = logging.getLogger(__name__)

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


async def _ensure_broll(db: Session, clip: Clip) -> None:
    """Auto-source B-roll for a clip that has none, before it renders.

    Without this, a clip only ever gets B-roll if the user opened the
    editor and pressed the button -- so the default export is a static
    talking head, and the B-roll feature effectively never fires. Sourcing
    here writes ordinary BrollAsset rows: they show up in the editor and
    can be removed or replaced before a re-export, which is what CLAUDE.md
    requires of any automatic insertion.

    Skipped entirely for a video submitted with B-roll switched off --
    that choice is the whole point of the toggle.

    Best-effort by design: no API keys, no search results, or a provider
    outage must not block the export.
    """

    if not settings.BROLL_AUTO_ON_EXPORT:
        return
    if clip.video_project is not None and not clip.video_project.auto_broll:
        # Switched off when the video was submitted: no B-roll unless the
        # user adds it themselves in the editor.
        return
    if not (settings.PEXELS_API_KEY or settings.PIXABAY_API_KEY):
        return

    existing = db.query(BrollAsset).filter(BrollAsset.clip_id == clip.id).count()
    if existing:
        return

    try:
        created = await auto_source_broll(db, clip)
    except Exception:
        logger.exception("Auto-sourcing B-roll failed for clip id=%s", clip.id)
        db.rollback()
        return

    if created:
        logger.info("Auto-sourced %d B-roll asset(s) for clip id=%s", len(created), clip.id)


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

    await _ensure_broll(db, clip)

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


@router.get("/{clip_id}/framing", response_model=ClipFramingResponse)
def clip_framing(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClipFramingResponse:
    """Where the speaker sits in the source, for the Speaker Focus preview.

    The editor previews a draft clip by streaming the *source* file and
    seeking client-side, so without this it can only guess at the framing
    -- a centre crop, which on a screen recording or an off-centre
    interview lands anywhere but on the person. Returning the same windows
    the renderer will use keeps the preview honest.

    Where two people are in conversation the response also carries the
    stretches that play as a split screen, so the preview can stack them
    the way the export will.

    Declared `def`, not `async def`, so FastAPI runs it in the threadpool:
    the probe is a bounded low-resolution ffmpeg read (a second or two,
    then cached per file and clip range), and it must not block the event
    loop while it runs. Rendering itself stays a background job.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)

    if clip.status == ClipStatus.ready and clip.video_file_path:
        # /preview serves the finished 9:16 export for a ready clip; it is
        # already framed on the speaker, so cropping it again would zoom in
        # on a crop.
        return ClipFramingResponse(clip_id=clip.id, mode="rendered")

    source_path = clip.video_project.source_file_path if clip.video_project else None
    if not source_path:
        raise NotFoundError("Source video")

    path = get_file_path(source_path)
    if not path.is_file():
        raise NotFoundError("Preview video file")

    framing = compute_speaker_framing(
        str(path),
        clip.start_time,
        max(clip.end_time - clip.start_time, 0.1),
        settings.RENDER_WIDTH,
        settings.RENDER_HEIGHT,
    )
    if framing is None:
        return ClipFramingResponse(clip_id=clip.id, mode="unavailable")

    def normalise(window: SpeakerWindow, crop_width: int, crop_height: int):  # type: ignore[no-untyped-def]
        return SpeakerFocusWindow(
            start_time=window.start_time,
            x=window.x / framing.source_width,
            y=window.y / framing.source_height,
            width=crop_width / framing.source_width,
            height=crop_height / framing.source_height,
            at_cut=window.at_cut,
        )

    split = framing.split
    return ClipFramingResponse(
        clip_id=clip.id,
        mode="speaker_focus",
        windows=[
            normalise(window, framing.crop_width, framing.crop_height)
            for window in framing.windows
        ],
        split_sections=[
            SplitScreenSection(
                start_time=section.start_time,
                end_time=section.end_time,
                panes=[
                    normalise(pane, split.crop_width, split.crop_height)
                    for pane in section.panes
                ],
            )
            for section in (split.sections if split else ())
        ],
    )


@router.get("/{clip_id}/captions", response_model=ClipCaptionsResponse)
def clip_captions(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClipCaptionsResponse:
    """The caption timeline this clip will be exported with.

    Captions come from the transcript unless the user wrote their own, so
    a clip that has never been edited still has plenty to say -- and the
    editor, which only knows about `caption_text`, would otherwise show a
    silent preview for a short that exports fully subtitled. Serving the
    render path's own timeline keeps the two in step, down to which word
    is lit up.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)
    duration = max(clip.end_time - clip.start_time, 0.1)
    segments = (
        list(clip.video_project.transcript_segments) if clip.video_project else []
    )

    events = _caption_events(
        caption_text=clip.caption_text,
        transcript_segments=segments,
        clip_start=clip.start_time,
        duration=duration,
    )
    style = CAPTION_STYLES.get(clip.caption_style.value)

    return ClipCaptionsResponse(
        clip_id=clip.id,
        style=clip.caption_style,
        events=[
            CaptionFrame(
                start_time=start, end_time=end, text=text, active_word=active_word
            )
            for start, end, text, active_word in caption_frames(events, style)
        ],
    )


@router.get("/{clip_id}/thumbnail")
async def clip_thumbnail(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_for_media),
) -> FileResponse:
    """Serve the poster frame written during export.

    Auth is via `?token=` for the same reason as /preview: an <img> tag
    can't send an Authorization header.

    Raises:
        NotFoundError: the clip has never been exported, or the poster
            frame is missing on disk.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)

    if not clip.thumbnail_path:
        raise NotFoundError("Clip thumbnail")

    path = Path(clip.thumbnail_path)
    if not path.is_file():
        raise NotFoundError("Clip thumbnail")

    return FileResponse(path=path, media_type="image/jpeg")


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
