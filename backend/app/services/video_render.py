"""Clip rendering: ffmpeg pipeline for the Export & Publish module.

Owned by BACKEND-AGENT (Export & Publish module). Invoked from
app/routers/exports.py via app.services.task_queue -- a real Redis-backed
job in production, run by the separate `worker` process/container, or
FastAPI's BackgroundTasks locally -- so the actual ffmpeg work never blocks
a request handler (see CLAUDE.md: never run long video processing
synchronously in a request handler).

Design notes / trade-offs (see also the summary in the PR description):

- `render_clip` is a *sync* function taking just `clip_id: int` (not a live
  `Clip`/`Session`) -- a cross-process job queue can't pickle a live ORM
  object, and the clip needs re-fetching fresh regardless, since by the
  time any background job actually runs, the request that scheduled it has
  long since closed its own session. This module always opens its *own*
  fresh `SessionLocal()` session and re-fetches the clip by id.
- 9:16 conversion is a simple scale+pad (letterbox/pillarbox) to a fixed
  1080x1920 canvas -- not a smart/AI reframe or crop-to-subject.
- Caption burn-in renders `clip.caption_text` as a single static,
  centered-bottom overlay for the whole clip duration via ffmpeg `drawtext`.
  It is not word-timed/karaoke-synced to the transcript, and long text is
  not auto-wrapped -- an MVP simplification per the task spec.
- B-roll is best-effort picture-in-picture: each `BrollAsset` is overlaid
  in the top-right corner during its [position_start, position_end] window,
  which is interpreted as **seconds relative to the exported clip's own
  timeline** (0 = clip start), since that's the only coordinate space this
  module can reason about without coupling to the B-roll module's
  internals. Every legitimately-created BrollAsset.asset_url is a remote
  Pexels/Pixabay http(s) URL (see BrollInsertRequest's validator in
  app.schemas.broll), so each is downloaded to a per-render temp directory
  before compositing (see _download_remote_broll) -- a failed download for
  one asset just skips that overlay (logged) rather than failing the whole
  render. A bare local-path fallback is kept for defense in depth / future
  local-asset support. Audio from B-roll assets is never mixed in -- only
  the source clip's original audio track is kept.
- Any failure (bad input, ffmpeg missing, ffmpeg error, unexpected
  exception) is caught so the background task never crashes silently; the
  clip's status is always left in a terminal state (`ready` or `failed`).
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import ffmpeg
import httpx
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models.broll_asset import BrollAsset
from app.models.clip import Clip, ClipStatus
from app.services.storage import UPLOAD_ROOT, get_file_path

logger = logging.getLogger(__name__)

# backend/app/services/video_render.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
EXPORTS_DIR = _BACKEND_DIR / "uploads" / "exports"

# Output canvas for the 9:16 short-form target.
_TARGET_WIDTH = 1080
_TARGET_HEIGHT = 1920

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# Corner reserved for B-roll picture-in-picture overlays.
_PIP_WIDTH = 360
_PIP_MARGIN = 24

# Bounds for downloading a remote B-roll asset before compositing it.
_BROLL_DOWNLOAD_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_MAX_BROLL_DOWNLOAD_BYTES = 200 * 1024 * 1024  # 200MB
_BROLL_CHUNK_SIZE = 1024 * 1024


def render_clip(clip_id: int) -> None:
    """Render the clip with id `clip_id` to an exportable 9:16 MP4 and
    persist the result.

    Runs synchronously (invoked as a background job -- see the module
    docstring). Always leaves `clip.status` in a terminal state (`ready` or
    `failed`) and never raises -- callers can fire this and forget it.
    """

    session = SessionLocal()
    try:
        fresh_clip = (
            session.query(Clip)
            .options(
                joinedload(Clip.broll_assets),
                joinedload(Clip.video_project),
            )
            .filter(Clip.id == clip_id)
            .first()
        )
        if fresh_clip is None:
            logger.error("render_clip: clip id=%s no longer exists; aborting", clip_id)
            return

        _render_and_persist(session, fresh_clip)
    except Exception:
        logger.exception("render_clip: unhandled error rendering clip id=%s", clip_id)
        _mark_failed_best_effort(session, clip_id)
    finally:
        session.close()


def _mark_failed_best_effort(session: Session, clip_id: int) -> None:
    """Last-resort attempt to flag a clip as failed after an unexpected error."""

    try:
        session.rollback()
        clip = session.query(Clip).filter(Clip.id == clip_id).first()
        if clip is not None:
            clip.status = ClipStatus.failed
            session.commit()
    except Exception:
        logger.exception(
            "render_clip: failed to mark clip id=%s as failed after an earlier error",
            clip_id,
        )


def _render_and_persist(session: Session, clip: Clip) -> None:
    """Validate inputs, run ffmpeg, and update `clip` with the outcome."""

    video_project = clip.video_project
    relative_source_path = video_project.source_file_path if video_project else None
    # source_file_path is stored relative to UPLOAD_ROOT (see app.services.storage) --
    # it must be resolved through get_file_path(), same as every other consumer,
    # rather than treated as a path in its own right.
    source_path = (
        str(get_file_path(relative_source_path)) if relative_source_path else None
    )

    if not source_path or not Path(source_path).is_file():
        logger.error(
            "render_clip: clip id=%s has no valid source_file_path (video_project_id=%s, "
            "path=%r)",
            clip.id,
            clip.video_project_id,
            relative_source_path,
        )
        clip.status = ClipStatus.failed
        session.commit()
        return

    duration = clip.end_time - clip.start_time
    if duration <= 0:
        logger.error(
            "render_clip: clip id=%s has invalid trim window [%s, %s]",
            clip.id,
            clip.start_time,
            clip.end_time,
        )
        clip.status = ClipStatus.failed
        session.commit()
        return

    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EXPORTS_DIR / f"{uuid.uuid4()}.mp4"

    try:
        with tempfile.TemporaryDirectory(prefix="broll_") as broll_tmp_dir:
            _run_ffmpeg(
                source_path=source_path,
                start_time=clip.start_time,
                duration=duration,
                caption_text=clip.caption_text,
                broll_assets=list(clip.broll_assets),
                output_path=output_path,
                broll_tmp_dir=Path(broll_tmp_dir),
            )
    except FileNotFoundError:
        logger.error(
            "render_clip: clip id=%s failed -- ffmpeg is not installed on this machine",
            clip.id,
        )
        clip.status = ClipStatus.failed
        session.commit()
        return
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        logger.error("render_clip: clip id=%s ffmpeg error: %s", clip.id, stderr)
        clip.status = ClipStatus.failed
        session.commit()
        return
    except Exception:
        logger.exception("render_clip: clip id=%s unexpected rendering failure", clip.id)
        clip.status = ClipStatus.failed
        session.commit()
        return

    clip.video_file_path = str(output_path)
    clip.status = ClipStatus.ready
    session.commit()
    logger.info("render_clip: clip id=%s rendered successfully -> %s", clip.id, output_path)


def _run_ffmpeg(
    *,
    source_path: str,
    start_time: float,
    duration: float,
    caption_text: str | None,
    broll_assets: list[BrollAsset],
    output_path: Path,
    broll_tmp_dir: Path,
) -> None:
    """Build and execute the ffmpeg filter graph for one clip.

    Raises FileNotFoundError if the ffmpeg binary is missing, or
    ffmpeg.Error if ffmpeg runs but exits non-zero.
    """

    main_input = ffmpeg.input(source_path, ss=start_time, t=duration)

    video_stream: Any = main_input.video.filter(
        "scale",
        _TARGET_WIDTH,
        _TARGET_HEIGHT,
        force_original_aspect_ratio="decrease",
    ).filter(
        "pad",
        _TARGET_WIDTH,
        _TARGET_HEIGHT,
        "(ow-iw)/2",
        "(oh-ih)/2",
        color="black",
    )

    if caption_text:
        video_stream = video_stream.filter(
            "drawtext",
            text=caption_text,
            fontsize=54,
            fontcolor="white",
            box=1,
            boxcolor="black@0.55",
            boxborderw=16,
            x="(w-text_w)/2",
            y="h-th-96",
            line_spacing=8,
        )

    pip_x = _TARGET_WIDTH - _PIP_WIDTH - _PIP_MARGIN
    for asset in broll_assets:
        local_path = _resolve_broll_path(asset.asset_url, broll_tmp_dir)
        if local_path is None:
            logger.warning(
                "render_clip: skipping broll asset id=%s (could not resolve or "
                "download %r)",
                asset.id,
                asset.asset_url,
            )
            continue

        window_start = max(0.0, asset.position_start)
        window_end = min(duration, asset.position_end)
        if window_end <= window_start:
            logger.warning(
                "render_clip: skipping broll asset id=%s (empty/out-of-range window "
                "[%s, %s] for clip duration %s)",
                asset.id,
                asset.position_start,
                asset.position_end,
                duration,
            )
            continue

        is_image = local_path.suffix.lower() in _IMAGE_SUFFIXES
        window_duration = window_end - window_start
        if is_image:
            broll_input = ffmpeg.input(str(local_path), loop=1, t=window_duration)
        else:
            broll_input = ffmpeg.input(str(local_path), t=window_duration)

        pip_stream = broll_input.video.filter("scale", _PIP_WIDTH, -1)
        video_stream = ffmpeg.overlay(
            video_stream,
            pip_stream,
            x=pip_x,
            y=_PIP_MARGIN,
            enable=f"between(t,{window_start},{window_end})",
        )

    _encode(video_stream, main_input, output_path)


def _encode(video_stream: Any, main_input: Any, output_path: Path) -> None:
    """Run the encode, falling back to a video-only output if the source
    has no audio track (rather than failing the whole render)."""

    try:
        (
            ffmpeg.output(
                video_stream,
                main_input.audio,
                str(output_path),
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                movflags="+faststart",
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        if "does not contain any stream" in stderr or "Stream map" in stderr:
            logger.warning(
                "render_clip: source has no usable audio stream, encoding video-only"
            )
            (
                ffmpeg.output(
                    video_stream,
                    str(output_path),
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    movflags="+faststart",
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        else:
            raise


def _resolve_broll_path(asset_url: str, tmp_dir: Path) -> Path | None:
    """Return a local filesystem Path to composite for `asset_url`.

    Every legitimately-created BrollAsset.asset_url is a remote Pexels/
    Pixabay http(s) URL (see BrollInsertRequest's validator in
    app.schemas.broll) -- download it into `tmp_dir` so ffmpeg can read it.
    A bare local-path fallback is kept for defense in depth / future local-
    asset support, deliberately confined to UPLOAD_ROOT (never an attacker-
    chosen absolute path) so a resolved "local" asset can never point
    outside the app's own upload tree even if that constraint upstream is
    ever loosened.
    """

    if asset_url.startswith(("http://", "https://")):
        return _download_remote_broll(asset_url, tmp_dir)

    path = (UPLOAD_ROOT / asset_url).resolve()
    try:
        path.relative_to(UPLOAD_ROOT.resolve())
    except ValueError:
        logger.warning(
            "Rejected broll asset_url %r: resolves outside UPLOAD_ROOT", asset_url
        )
        return None
    if path.is_file():
        return path
    return None


def _download_remote_broll(url: str, dest_dir: Path) -> Path | None:
    """Download a remote B-roll asset to `dest_dir` for ffmpeg to composite.

    Returns None (logging a warning) on any failure -- one bad/unreachable
    B-roll asset should never fail the whole clip render.
    """

    suffix = Path(urlparse(url).path).suffix or ".mp4"
    dest_path = dest_dir / f"{uuid.uuid4().hex}{suffix}"

    try:
        with (
            httpx.Client(timeout=_BROLL_DOWNLOAD_TIMEOUT, follow_redirects=True) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            size = 0
            with dest_path.open("wb") as out_file:
                for chunk in response.iter_bytes(_BROLL_CHUNK_SIZE):
                    size += len(chunk)
                    if size > _MAX_BROLL_DOWNLOAD_BYTES:
                        raise ValueError("B-roll asset exceeds max download size")
                    out_file.write(chunk)
    except Exception as exc:
        logger.warning("Could not download B-roll asset from %r: %s", url, exc)
        dest_path.unlink(missing_ok=True)
        return None

    if dest_path.stat().st_size == 0:
        dest_path.unlink(missing_ok=True)
        return None
    return dest_path
