"""Export & Publish endpoints: render, poll status, download, and YouTube Shorts caption package.

Owned by BACKEND-AGENT (Export & Publish module). Registered under the
`/clips` prefix so the final paths are /clips/{id}/export,
/clips/{id}/export/status, /clips/{id}/download, and
/clips/{id}/youtube-caption -- the Clip Library module (app/routers/clips.py)
owns /clips, /clips/{id}, and /clips/{id}/reorder and does not define these
sub-paths.

Ownership of a clip is checked directly against the Clip model here
(rather than importing the Clip Library module's service layer) to avoid
cross-module coupling, per the module's file-ownership boundaries.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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
    YouTubeCaptionPackageResponse,
    YouTubeCaptionRequest,
)
from app.services import task_queue
from app.services.broll_sourcing import auto_source_broll
from app.services.caption_render import CAPTION_STYLES, caption_frames
from app.services.clip_service import _REVIEW_THRESHOLD, score_clip_partial
from app.services.reframe import SpeakerWindow, compute_speaker_framing
from app.services.storage import get_file_path
from app.services.video_render import _caption_events, render_clip
from app.services.youtube_metadata import generate_youtube_caption_package

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
    force: bool = Query(
        False,
        description=(
            "Set true to bypass the viral score gate and render anyway "
            "when a clip scores below the virality threshold (50.0)."
        ),
    ),
    copyright_safe: bool = Query(
        False,
        description=(
            "Set true to render in Copyright-Safe / Fair-Use Transformative "
            "mode (trims raw hook to <=7.5s, applies audio/visual fingerprint "
            "protection, and appends original AI commentary voiceover over "
            "full-screen B-roll cutaways)."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExportStatusResponse:
    """Kick off rendering a clip into an exportable, downloadable MP4.

    Pipeline gate: checks that the clip contains verified viral content
    (virality_score >= 50.0). If the score is below the threshold and
    `force` is false, returns 409 Conflict without rendering so weak
    clips are not created into videos.
    """

    clip = _get_owned_clip(db, clip_id, current_user.id)

    # Score any clip that slipped through without one (legacy/pre-migration rows)
    if clip.virality_score is None:
        segments = clip.video_project.transcript_segments if clip.video_project else []
        score_clip_partial(clip, segments)
        db.commit()
        db.refresh(clip)

    below_threshold = (
        clip.virality_score is not None
        and clip.virality_score < _REVIEW_THRESHOLD
    )

    if below_threshold and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "score_below_threshold",
                "virality_score": clip.virality_score,
                "threshold": _REVIEW_THRESHOLD,
                "message": (
                    f"This clip scored {clip.virality_score:.0f}/100, which is below "
                    f"the {_REVIEW_THRESHOLD:.0f}-point virality threshold. "
                    "Video creation is gated because the clip lacks verified viral content. "
                    "Pass ?force=true to render anyway."
                ),
            },
        )

    await _ensure_broll(db, clip)

    clip.status = ClipStatus.rendering
    db.commit()
    db.refresh(clip)

    effective_copyright_safe = bool(copyright_safe or settings.RENDER_COPYRIGHT_SAFE)
    if copyright_safe:
        task_queue.enqueue(background_tasks, render_clip, clip.id, True)
    else:
        task_queue.enqueue(background_tasks, render_clip, clip.id)

    return ExportStatusResponse(
        clip_id=clip.id,
        status=clip.status,
        video_file_path=clip.video_file_path,
        virality_score=clip.virality_score,
        below_threshold=below_threshold,
        copyright_safe=effective_copyright_safe,
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
        clip_id=clip.id,
        status=clip.status,
        video_file_path=clip.video_file_path,
        virality_score=clip.virality_score,
        below_threshold=(
            clip.virality_score is not None
            and clip.virality_score < _REVIEW_THRESHOLD
        ),
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
    """Where the speaker sits in the source, for the Speaker Focus preview."""

    clip = _get_owned_clip(db, clip_id, current_user.id)

    if clip.status == ClipStatus.ready and clip.video_file_path:
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

    def normalise(
        window: SpeakerWindow, crop_width: int, crop_height: int
    ) -> SpeakerFocusWindow:
        return SpeakerFocusWindow(
            start_time=window.start_time,
            x=window.x / framing.source_width,
            y=window.y / framing.source_height,
            width=crop_width / framing.source_width,
            height=crop_height / framing.source_height,
            at_cut=window.at_cut,
        )

    split = framing.split
    split_sections: list[SplitScreenSection] = []
    if split is not None:
        split_sections = [
            SplitScreenSection(
                start_time=section.start_time,
                end_time=section.end_time,
                panes=[
                    normalise(pane, split.crop_width, split.crop_height)
                    for pane in section.panes
                ],
            )
            for section in split.sections
        ]

    return ClipFramingResponse(
        clip_id=clip.id,
        mode="speaker_focus",
        windows=[
            normalise(window, framing.crop_width, framing.crop_height)
            for window in framing.windows
        ],
        split_sections=split_sections,
    )


@router.get("/{clip_id}/captions", response_model=ClipCaptionsResponse)
def clip_captions(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ClipCaptionsResponse:
    """The caption timeline this clip will be exported with."""

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


@router.get(
    "/{clip_id}/youtube-caption",
    response_model=YouTubeCaptionPackageResponse,
)
def get_youtube_caption_package(
    clip_id: int,
    tone: str = Query(
        "viral",
        description=(
            "Tone for YouTube caption package "
            "(viral, educational, storytelling, professional)."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> YouTubeCaptionPackageResponse:
    """Fetch or generate the YouTube Shorts caption, title, description, and content preview."""

    clip = _get_owned_clip(db, clip_id, current_user.id)
    segments = (
        list(clip.video_project.transcript_segments) if clip.video_project else []
    )
    package = generate_youtube_caption_package(
        clip,
        segments,
        tone=tone,
        include_hashtags=True,
        include_timestamps=True,
    )
    return YouTubeCaptionPackageResponse(**package)


@router.post(
    "/{clip_id}/youtube-caption",
    response_model=YouTubeCaptionPackageResponse,
)
def create_youtube_caption_package(
    clip_id: int,
    payload: YouTubeCaptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> YouTubeCaptionPackageResponse:
    """Generate or customize a YouTube Shorts caption & content package for a clip."""

    clip = _get_owned_clip(db, clip_id, current_user.id)
    if payload.custom_caption_text is not None and payload.apply_caption_to_clip:
        clip.caption_text = payload.custom_caption_text.strip() or None
        db.commit()
        db.refresh(clip)

    segments = (
        list(clip.video_project.transcript_segments) if clip.video_project else []
    )
    package = generate_youtube_caption_package(
        clip,
        segments,
        tone=payload.tone,
        include_hashtags=payload.include_hashtags,
        include_timestamps=payload.include_timestamps,
    )
    if payload.apply_caption_to_clip and not clip.caption_text and package["caption_text"]:
        clip.caption_text = str(package["caption_text"])
        db.commit()
        db.refresh(clip)

    return YouTubeCaptionPackageResponse(**package)


@router.get("/{clip_id}/thumbnail")
async def clip_thumbnail(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_for_media),
) -> FileResponse:
    """Serve the poster frame written during export."""

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
    current_user: User = Depends(get_current_user_for_media),
) -> FileResponse:
    """Stream the rendered MP4 as an attachment, once export has completed."""

    clip = _get_owned_clip(db, clip_id, current_user.id)

    if clip.status != ClipStatus.ready or not clip.video_file_path:
        raise ValidationAppError("Clip export is not ready for download yet")

    path = Path(clip.video_file_path)
    if not path.is_file():
        raise NotFoundError("Exported video file")

    safe_title = _UNSAFE_FILENAME_CHARS.sub("-", clip.title).strip("-")[:60] or "clip"
    filename = f"{safe_title}-{clip.id}.mp4"

    return FileResponse(path=path, media_type="video/mp4", filename=filename)
