"""Clip rendering: broadcast-quality ffmpeg pipeline for the Export & Publish module.

Owned by BACKEND-AGENT (Export & Publish module). Invoked from
app/routers/exports.py via app.services.task_queue -- a real Redis-backed
job in production, run by the separate `worker` process/container, or
FastAPI's BackgroundTasks locally -- so the actual ffmpeg work never blocks
a request handler (see CLAUDE.md: never run long video processing
synchronously in a request handler).

The output targets YouTube Shorts' recommended upload specs so a rendered
clip can be uploaded as-is without YouTube having to re-encode from a
lossy intermediate:

- 1080x1920 (9:16), square pixels, constant frame rate (30fps default)
- H.264 High profile, CRF-based encode, yuv420p, BT.709 colour tags
- 2-second GOP (keyframe interval = 2x fps), `+faststart` for streaming
- AAC-LC stereo @ 192kbps / 48kHz, loudness-normalised to -14 LUFS
  (YouTube's playback target, so the clip isn't turned down on upload)

Everything above is tunable through `RENDER_*` environment variables --
see app.config.Settings and .env.example.

Design notes / trade-offs:

- `render_clip` is a *sync* function taking just `clip_id: int` (not a live
  `Clip`/`Session`) -- a cross-process job queue can't pickle a live ORM
  object, and the clip needs re-fetching fresh regardless, since by the
  time any background job actually runs, the request that scheduled it has
  long since closed its own session. This module always opens its *own*
  fresh `SessionLocal()` session and re-fetches the clip by id.
- 9:16 framing has four modes (`RENDER_FRAMING`): `auto` (default) finds
  the speaker in the footage and crops to them, zooming in when they are
  small in frame -- a webcam bubble on a screen recording -- splitting the
  screen between stacked panes for the stretches where two people are in
  conversation, and falling back to `blur` when no subject stands out
  (see app.services.reframe);
  `blur` fills the frame with a blurred, darkened copy of the source
  behind the fitted image -- the standard short-form look, and far better
  than black bars for a 16:9 broadcast source; `crop` centre-crops to fill
  (full bleed, but cuts the sides off); `pad` keeps the old black
  letterbox.
- Captions are **time-synced**, not one static overlay: transcript
  segments overlapping the clip window are split into short, readable
  chunks and burned in on their own timing (see `_caption_events`). A
  user-edited `clip.caption_text` overrides the transcript and is spread
  across the clip's duration instead. Rendered through libass (`ass`
  filter) when the local ffmpeg has it, else `drawtext`; if the ffmpeg
  build has neither, captions are skipped with a warning rather than
  failing the export (see `_caption_backend`).
- B-roll is best-effort: each `BrollAsset` is shown during its
  [position_start, position_end] window, which is interpreted as
  **seconds relative to the exported clip's own timeline** (0 = clip
  start), since that's the only coordinate space this module can reason
  about without coupling to the B-roll module's internals. `RENDER_BROLL_MODE`
  picks `pip` (default; a bordered picture-in-picture card in the top
  corner) or `fullscreen` (a full-frame cutaway, the more editorial look).
  Every legitimately-created BrollAsset.asset_url is a remote Pexels/
  Pixabay http(s) URL (see BrollInsertRequest's validator in
  app.schemas.broll), so each is downloaded to a per-render temp directory
  before compositing (see _download_remote_broll) -- a failed download for
  one asset just skips that overlay (logged) rather than failing the whole
  render. A bare local-path fallback is kept for defense in depth / future
  local-asset support. Audio from B-roll assets is never mixed in -- only
  the source clip's original audio track is kept.
- A poster frame is written alongside the MP4 and stored on
  `clip.thumbnail_path`, served by GET /clips/{id}/thumbnail -- handy both
  for the clip library grid and as a YouTube custom thumbnail starting point.
- Any failure (bad input, ffmpeg missing, ffmpeg error, unexpected
  exception) is caught so the background task never crashes silently; the
  clip's status is always left in a terminal state (`ready` or `failed`).
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import ffmpeg
import httpx
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal
from app.models.broll_asset import BrollAsset
from app.models.clip import Clip, ClipCaptionStyle, ClipFraming, ClipStatus
from app.models.transcript_segment import TranscriptSegment
from app.models.video_project import VideoProject
from app.services.caption_render import render_caption_images
from app.services.reframe import (
    SpeakerFraming,
    compute_speaker_framing,
    crop_expressions,
)
from app.services.storage import UPLOAD_ROOT, get_file_path

logger = logging.getLogger(__name__)

# How long the split screen takes to dissolve in over the single-speaker
# frame, and back out again at the end of a stretch. Kept short: this is a
# soft landing on a layout change, not a transition effect.
_SPLIT_FADE_SECONDS = 0.25

# How long a caption image is held past its window, to cover the frame
# where the next one is still arriving. See _apply_captions.
_CAPTION_HANDOVER_SECONDS = 0.12

# backend/app/services/video_render.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
EXPORTS_DIR = _BACKEND_DIR / "uploads" / "exports"

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

# Bounds for downloading a remote B-roll asset before compositing it.
_BROLL_DOWNLOAD_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_MAX_BROLL_DOWNLOAD_BYTES = 200 * 1024 * 1024  # 200MB
_BROLL_CHUNK_SIZE = 1024 * 1024

# Caption layout/timing. Chunks are kept short so a burned-in line never
# needs to wrap on a 1080-wide frame and stays readable at phone size.
_CAPTION_MAX_CHARS = 30
_CAPTION_MAX_WORDS = 6
_CAPTION_MIN_SECONDS = 0.7

# One line of `ffmpeg -filters` output, e.g. " TS gblur  V->V  Apply Gaussian
# Blur filter." The flags column is 2 or 3 characters wide depending on the
# ffmpeg version, so the "in->out" column is what actually identifies a real
# filter row (and excludes the legend lines above the table).
_FILTER_LINE_RE = re.compile(r"^\s*[A-Z.]{2,3}\s+(\S+)\s+\S+->\S+", re.MULTILINE)

# ASS section headers. Kept as module constants because the format lines
# are fixed by the ASS spec and must each stay on a single line.
_ASS_STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
    "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
    "MarginL, MarginR, MarginV, Encoding\n"
)
_ASS_EVENT_FORMAT = (
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, Effect, Text\n"
)

# Font files tried (in order) for the `drawtext` caption fallback, which
# needs a real file rather than a fontconfig family name. Covers the
# Debian-based production image and a macOS dev machine.
_FONT_FILE_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Bold.ttf",
)


def render_clip(clip_id: int) -> None:
    """Render the clip with id `clip_id` to an upload-ready 9:16 MP4 and
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
                joinedload(Clip.video_project).joinedload(
                    VideoProject.transcript_segments
                ),
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

    transcript_segments = (
        list(video_project.transcript_segments) if video_project else []
    )
    captions = _caption_events(
        caption_text=clip.caption_text,
        transcript_segments=transcript_segments,
        clip_start=clip.start_time,
        duration=duration,
    )

    try:
        with tempfile.TemporaryDirectory(prefix="render_") as tmp_dir:
            _run_ffmpeg(
                source_path=source_path,
                start_time=clip.start_time,
                duration=duration,
                captions=captions,
                broll_assets=list(clip.broll_assets),
                output_path=output_path,
                tmp_dir=Path(tmp_dir),
                framing=_framing_mode(clip),
                caption_style=clip.caption_style,
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
    thumbnail_path = _extract_thumbnail(output_path, duration)
    if thumbnail_path is not None:
        clip.thumbnail_path = str(thumbnail_path)
    clip.status = ClipStatus.ready
    session.commit()
    logger.info("render_clip: clip id=%s rendered successfully -> %s", clip.id, output_path)


# ---------------------------------------------------------------------------
# ffmpeg capability probing
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _available_filters() -> frozenset[str]:
    """Names of the filters the locally installed ffmpeg was built with.

    ffmpeg builds vary in which optional libraries they were compiled
    against -- notably libass (`ass`/`subtitles`) and libfreetype
    (`drawtext`), both of which some Homebrew/minimal builds omit. Probing
    once lets the render degrade gracefully instead of failing an export
    with an opaque "No such filter" error.
    """

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("Could not probe ffmpeg filters: %s", exc)
        return frozenset()

    return frozenset(
        match.group(1) for match in _FILTER_LINE_RE.finditer(result.stdout)
    )


@lru_cache(maxsize=1)
def _caption_backend() -> str | None:
    """Which burn-in mechanism to use: "image", "ass", "drawtext", or None.

    Rasterised PNG overlays come first deliberately. They only need
    `overlay`, which every ffmpeg build has, so captions look identical on a
    developer's Homebrew ffmpeg and in the production container -- whereas
    `ass` and `drawtext` are optional at compile time and their absence
    silently produces an uncaptioned Short. The ffmpeg-native filters stay
    as fallbacks for a deployment without Pillow or a usable font.
    """

    filters = _available_filters()

    if "overlay" in filters and _pillow_available() and _caption_font_file():
        return "image"
    if "ass" in filters:
        return "ass"
    if "drawtext" in filters:
        return "drawtext"

    logger.warning(
        "No caption backend available: this ffmpeg has neither 'ass' (libass) nor "
        "'drawtext' (libfreetype), and Pillow/a TrueType font could not be found -- "
        "clips will render without burned-in captions. Install Pillow, or an ffmpeg "
        "built with libass."
    )
    return None


@lru_cache(maxsize=1)
def _pillow_available() -> bool:
    """Whether Pillow can be imported for rasterising captions."""

    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _caption_font_file() -> str | None:
    """Path to a font file for the `drawtext` fallback, if one can be found."""

    if settings.RENDER_CAPTION_FONT_FILE:
        configured = Path(settings.RENDER_CAPTION_FONT_FILE)
        if configured.is_file():
            return str(configured)
        logger.warning(
            "RENDER_CAPTION_FONT_FILE=%r does not exist; falling back to a system font",
            settings.RENDER_CAPTION_FONT_FILE,
        )

    for candidate in _FONT_FILE_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------


def _chunk_caption_text(text: str) -> list[str]:
    """Split caption text into short, single-line-friendly chunks.

    Burning a whole transcript sentence in at once produces a wall of text
    that either overflows a 1080px frame or has to be shrunk to be
    unreadable on a phone. Short chunks (a few words each) are what
    short-form captions actually look like.
    """

    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = [*current, word]
        candidate_len = len(" ".join(candidate))
        if current and (
            candidate_len > _CAPTION_MAX_CHARS or len(candidate) > _CAPTION_MAX_WORDS
        ):
            chunks.append(" ".join(current))
            current = [word]
        else:
            current = candidate
    if current:
        chunks.append(" ".join(current))
    return chunks


def _distribute(
    chunks: list[str], start: float, end: float
) -> list[tuple[float, float, str]]:
    """Spread `chunks` across [start, end], weighted by their length.

    Longer chunks take proportionally longer to read, so weighting by
    character count keeps the captions roughly in sync with speech even
    though the transcript only gives us segment-level (not word-level)
    timing.
    """

    span = end - start
    if span <= 0 or not chunks:
        return []

    total_chars = sum(len(chunk) for chunk in chunks) or len(chunks)
    events: list[tuple[float, float, str]] = []
    cursor = start
    for index, chunk in enumerate(chunks):
        weight = (len(chunk) or 1) / total_chars
        chunk_end = end if index == len(chunks) - 1 else cursor + span * weight
        events.append((cursor, min(chunk_end, end), chunk))
        cursor = chunk_end
    return events


def _caption_events(
    *,
    caption_text: str | None,
    transcript_segments: list[TranscriptSegment],
    clip_start: float,
    duration: float,
) -> list[tuple[float, float, str]]:
    """Build the (start, end, text) caption timeline for one clip.

    Times are relative to the exported clip (0 = clip start). A
    user-supplied `caption_text` wins -- it's an explicit override edited
    in the clip editor -- and is spread across the whole clip. Otherwise
    the transcript segments overlapping the clip's trim window are used, so
    the burned-in captions actually follow what is being said.
    """

    if caption_text and caption_text.strip():
        return _distribute(_chunk_caption_text(caption_text.strip()), 0.0, duration)

    clip_end = clip_start + duration
    events: list[tuple[float, float, str]] = []
    for segment in sorted(transcript_segments, key=lambda s: s.start_time):
        if segment.end_time <= clip_start or segment.start_time >= clip_end:
            continue
        text = (segment.text or "").strip()
        if not text:
            continue
        rel_start = max(0.0, segment.start_time - clip_start)
        rel_end = min(duration, segment.end_time - clip_start)
        if rel_end - rel_start < 0.2:
            continue
        events.extend(_distribute(_chunk_caption_text(text), rel_start, rel_end))

    # Guarantee a minimum on-screen time without ever letting one caption
    # run past the next one's start (libass/drawtext would overlap them).
    adjusted: list[tuple[float, float, str]] = []
    for index, (start, end, text) in enumerate(events):
        next_start = events[index + 1][0] if index + 1 < len(events) else duration
        adjusted.append((start, min(max(end, start + _CAPTION_MIN_SECONDS), next_start), text))
    return [event for event in adjusted if event[1] > event[0]]


def _ass_timestamp(seconds: float) -> str:
    """Format seconds as ASS's H:MM:SS.cc timestamp."""

    seconds = max(0.0, seconds)
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis == 100:  # rounding carry
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _write_ass_file(
    events: list[tuple[float, float, str]], path: Path, width: int, height: int
) -> None:
    """Write the caption timeline as an ASS subtitle file for libass.

    Styled for short-form: heavy weight, white on a thick black outline
    (readable over any footage), bottom-centred but lifted clear of the
    YouTube Shorts UI overlay along the bottom of the screen.
    """

    font_size = max(28, int(height * settings.RENDER_CAPTION_SCALE))
    margin_v = int(height * settings.RENDER_CAPTION_MARGIN_RATIO)
    outline = max(2, font_size // 12)
    shadow = max(1, font_size // 24)

    style = (
        f"Style: Short,{settings.RENDER_CAPTION_FONT},{font_size},"
        # PrimaryColour (white), SecondaryColour, OutlineColour (black),
        # BackColour, then Bold=-1 (on).
        "&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,"
        f"1,{outline},{shadow},2,80,80,{margin_v},1"
    )

    lines = [
        "[Script Info]\n",
        "ScriptType: v4.00+\n",
        f"PlayResX: {width}\n",
        f"PlayResY: {height}\n",
        "WrapStyle: 0\n",
        "ScaledBorderAndShadow: yes\n",
        "YCbCr Matrix: TV.709\n",
        "\n[V4+ Styles]\n",
        _ASS_STYLE_FORMAT,
        style + "\n",
        "\n[Events]\n",
        _ASS_EVENT_FORMAT,
    ]
    for start, end, text in events:
        # `{...}` is ASS's inline style-override syntax and `\` starts an
        # escape, so neither may survive from transcript text into a
        # Dialogue line.
        safe_text = (
            text.replace("\\", "\\\\")
            .replace("\n", " ")
            .replace("{", "(")
            .replace("}", ")")
        )
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},"
            f"Short,,0,0,0,,{safe_text}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def _apply_captions(
    video_stream: Any,
    events: list[tuple[float, float, str]],
    tmp_dir: Path,
    caption_style: ClipCaptionStyle | None = None,
) -> Any:
    """Burn `events` into `video_stream` using whichever backend ffmpeg has.

    `caption_style` is the preset the clip was set to in the editor. It
    only reaches the rasteriser: the `ass`/`drawtext` fallbacks exist for
    ffmpeg builds that can't do better than plain text, and giving them
    half a look would be worse than giving them the plain one.
    """

    if not events:
        return video_stream

    backend = _caption_backend()
    if backend is None:
        return video_stream

    if backend == "image":
        images = render_caption_images(
            events,
            tmp_dir,
            settings.RENDER_WIDTH,
            settings.RENDER_HEIGHT,
            _caption_font_file(),
            caption_style.value if caption_style else None,
        )
        if images is not None:
            for image in images:
                # Each overlay is held a fraction past its window. Back to
                # back captions -- a style that lights up one word at a
                # time makes many -- otherwise flicker for a frame at every
                # handover, where the outgoing image has ended and the
                # incoming one's first frame has yet to arrive. Later
                # overlays sit on top, so the overlap is invisible.
                hold_until = image.end + _CAPTION_HANDOVER_SECONDS
                overlay_input = ffmpeg.input(
                    str(image.path),
                    loop=1,
                    t=max(hold_until - image.start, 0.05),
                )
                video_stream = ffmpeg.overlay(
                    video_stream,
                    overlay_input.video.filter(
                        "setpts", f"PTS-STARTPTS+{image.start:.3f}/TB"
                    ),
                    x=0,
                    y=image.y,
                    eof_action="pass",
                    enable=f"between(t,{image.start:.3f},{hold_until:.3f})",
                )
            return video_stream
        # Rasterising failed at render time (a font that loaded at probe
        # time but not now); fall through to the ffmpeg-native filters.
        logger.warning("Caption rasterisation failed; trying ffmpeg text filters")

    if backend == "ass" or "ass" in _available_filters():
        ass_path = tmp_dir / "captions.ass"
        _write_ass_file(
            events, ass_path, settings.RENDER_WIDTH, settings.RENDER_HEIGHT
        )
        return video_stream.filter("ass", str(ass_path))

    # drawtext fallback: one filter per caption, gated on its time window.
    # The text goes through `textfile` so no escaping of the transcript's
    # quotes/colons/commas is needed inside the filter graph.
    font_size = max(28, int(settings.RENDER_HEIGHT * settings.RENDER_CAPTION_SCALE))
    margin_v = int(settings.RENDER_HEIGHT * settings.RENDER_CAPTION_MARGIN_RATIO)
    font_file = _caption_font_file()

    for index, (start, end, text) in enumerate(events):
        text_path = tmp_dir / f"caption_{index:04d}.txt"
        text_path.write_text(text, encoding="utf-8")
        text_kwargs: dict[str, Any] = {
            "textfile": str(text_path),
            "fontsize": font_size,
            "fontcolor": "white",
            "borderw": max(2, font_size // 12),
            "bordercolor": "black@0.95",
            "shadowx": 0,
            "shadowy": max(1, font_size // 24),
            "shadowcolor": "black@0.6",
            "x": "(w-text_w)/2",
            "y": f"h-text_h-{margin_v}",
            "enable": f"between(t,{start:.3f},{end:.3f})",
        }
        if font_file:
            text_kwargs["fontfile"] = font_file
        else:
            text_kwargs["font"] = settings.RENDER_CAPTION_FONT
        video_stream = video_stream.filter("drawtext", **text_kwargs)
    return video_stream


# ---------------------------------------------------------------------------
# ffmpeg graph
# ---------------------------------------------------------------------------


def _frame_9x16(
    main_input: Any,
    *,
    source_path: str,
    start_time: float,
    duration: float,
    framing: str | None = None,
) -> Any:
    """Convert the source frame to the 9:16 canvas.

    `framing` is the clip's own choice from the editor, already mapped to
    this module's vocabulary by `_framing_mode`; without one it falls back
    to the RENDER_FRAMING default.
    """

    width = settings.RENDER_WIDTH
    height = settings.RENDER_HEIGHT
    framing = (framing or settings.RENDER_FRAMING).lower()
    filters = _available_filters()

    if framing == "auto":
        speaker = compute_speaker_framing(
            source_path, start_time, duration, width, height
        )
        if speaker is not None:
            return _speaker_framed(
                main_input, speaker, width, height, duration, filters
            )
        # No confident subject: the blurred fill shows the whole frame,
        # which is the safe answer when we don't know where to look.
        framing = "blur"

    if framing == "crop":
        return (
            main_input.video.filter(
                "scale", width, height, force_original_aspect_ratio="increase"
            )
            .filter("crop", width, height)
            .filter("setsar", 1)
        )

    if framing == "blur" and "gblur" in filters:
        split = main_input.video.filter_multi_output("split")
        background = (
            split[0]
            .filter("scale", width, height, force_original_aspect_ratio="increase")
            .filter("crop", width, height)
            .filter("gblur", sigma=settings.RENDER_BLUR_SIGMA)
            .filter("eq", brightness=-0.12, saturation=1.15)
        )
        foreground = split[1].filter(
            "scale", width, height, force_original_aspect_ratio="decrease"
        )
        return ffmpeg.overlay(
            background, foreground, x="(W-w)/2", y="(H-h)/2"
        ).filter("setsar", 1)

    if framing == "blur":
        logger.warning(
            "RENDER_FRAMING=blur requested but this ffmpeg has no 'gblur' filter; "
            "falling back to letterbox padding"
        )

    # `pad`: the plain letterbox.
    return (
        main_input.video.filter(
            "scale", width, height, force_original_aspect_ratio="decrease"
        )
        .filter("pad", width, height, "(ow-iw)/2", "(oh-ih)/2", color="black")
        .filter("setsar", 1)
    )


def _framing_mode(clip: Clip) -> str:
    """The framing this clip was set to in the editor, as a render mode.

    The editor speaks in outcomes (`speaker_focus`, `dynamic_blur`, `fit`)
    and this module in mechanisms (`auto`, `blur`, `pad`), so the two
    vocabularies meet here rather than leaking into each other.
    """

    return {
        ClipFraming.speaker_focus: "auto",
        ClipFraming.dynamic_blur: "blur",
        ClipFraming.fit: "pad",
    }.get(clip.framing_mode, settings.RENDER_FRAMING.lower())


def _speaker_framed(
    main_input: Any,
    framing: SpeakerFraming,
    width: int,
    height: int,
    duration: float,
    filters: set[str],
) -> Any:
    """Crop the source to the speaker, splitting the screen where two talk.

    The single-speaker window carries the clip; where the analysis found
    more than one person in the conversation, a stack of per-speaker panes
    is overlaid for exactly those stretches (`enable`), so the short cuts
    to a split screen and back the way an editor would rather than holding
    one layout for the whole clip. The panes dissolve in and out over a
    quarter of a second so the layout change lands softly.

    Crop x/y are time expressions that step wherever the framing moves, so
    they are passed to ffmpeg as strings.
    """

    crop_x, crop_y = crop_expressions(framing.windows)
    split = framing.split
    if split is not None and "vstack" not in filters:
        logger.warning(
            "this ffmpeg has no 'vstack' filter, so a clip with two speakers "
            "renders as a single-speaker crop instead of a split screen"
        )
        split = None

    if split is None:
        return (
            main_input.video.filter(
                "crop", framing.crop_width, framing.crop_height, crop_x, crop_y
            )
            .filter("scale", width, height)
            .filter("setsar", 1)
        )

    pane_height = (height // split.pane_count) & ~1
    streams = main_input.video.filter_multi_output("split", 1 + split.pane_count)
    base = (
        streams[0]
        .filter("crop", framing.crop_width, framing.crop_height, crop_x, crop_y)
        .filter("scale", width, height)
        .filter("setsar", 1)
    )

    panes = []
    for index in range(split.pane_count):
        pane_x, pane_y = crop_expressions(
            [section.panes[index] for section in split.sections]
        )
        panes.append(
            streams[index + 1]
            .filter("crop", split.crop_width, split.crop_height, pane_x, pane_y)
            .filter("scale", width, pane_height)
            .filter("setsar", 1)
        )

    stacked = ffmpeg.filter(panes, "vstack", inputs=split.pane_count)
    if pane_height * split.pane_count != height:
        # Rounding to even pane heights can leave a sliver; fill it rather
        # than letting the single-speaker frame show through the gap.
        stacked = stacked.filter("pad", width, height, 0, 0, color="black")

    # Dissolve the panes in and out over the single-speaker frame instead
    # of snapping to them. The fade sits just *inside* each stretch, so it
    # mixes two framings of the same footage rather than blending across
    # the cut that starts it. Each fade is fenced to its own window with
    # `enable`, otherwise a later one would blank everything before it.
    stacked = stacked.filter("format", "yuva420p")
    for section in split.sections:
        start, end = section.start_time, section.end_time
        # A clip that opens or ends mid-conversation is already in the
        # layout -- dissolving in from a frame nobody saw just looks like
        # the player stuttering on the first frames.
        if start > _SPLIT_FADE_SECONDS:
            stacked = stacked.filter(
                "fade",
                type="in",
                start_time=f"{start:.2f}",
                duration=f"{_SPLIT_FADE_SECONDS:.2f}",
                alpha=1,
                enable=f"between(t,{start:.2f},{start + _SPLIT_FADE_SECONDS:.2f})",
            )
        if end < duration - _SPLIT_FADE_SECONDS:
            stacked = stacked.filter(
                "fade",
                type="out",
                start_time=f"{end - _SPLIT_FADE_SECONDS:.2f}",
                duration=f"{_SPLIT_FADE_SECONDS:.2f}",
                alpha=1,
                enable=f"between(t,{end - _SPLIT_FADE_SECONDS:.2f},{end:.2f})",
            )

    shown = "+".join(
        f"between(t,{section.start_time:.2f},{section.end_time:.2f})"
        for section in split.sections
    )
    logger.info(
        "render: %d stretch(es) of this clip play as a %d-way split screen",
        len(split.sections),
        split.pane_count,
    )
    return ffmpeg.overlay(base, stacked, x=0, y=0, enable=shown).filter("setsar", 1)


def _apply_broll(
    video_stream: Any, broll_assets: list[BrollAsset], duration: float, tmp_dir: Path
) -> Any:
    """Composite each resolvable B-roll asset over the clip's timeline."""

    width = settings.RENDER_WIDTH
    height = settings.RENDER_HEIGHT
    fullscreen = settings.RENDER_BROLL_MODE.lower() == "fullscreen"
    pip_width = int(width * settings.RENDER_PIP_WIDTH_RATIO)
    pip_margin = int(width * 0.03)
    border = max(2, pip_width // 90)

    for asset in broll_assets:
        local_path = _resolve_broll_path(asset.asset_url, tmp_dir)
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
            # Stock clips are routinely shorter than the window they were
            # placed in. Without the loop the overlay simply runs out and
            # (via eof_action="pass") the cutaway vanishes mid-window,
            # which looks like the B-roll failed rather than a deliberate
            # cut; -t then trims the loop back to the window.
            broll_input = ffmpeg.input(
                str(local_path), stream_loop=-1, t=window_duration
            )

        if fullscreen:
            overlay_stream = (
                broll_input.video.filter(
                    "scale", width, height, force_original_aspect_ratio="increase"
                )
                .filter("crop", width, height)
                .filter("setsar", 1)
            )
            overlay_x, overlay_y = 0, 0
        else:
            overlay_stream = (
                broll_input.video.filter("scale", pip_width - 2 * border, -2)
                .filter("setsar", 1)
                # A thin white frame reads as a deliberate inset card rather
                # than a stray video pasted on top of the shot.
                .filter(
                    "pad",
                    f"iw+{2 * border}",
                    f"ih+{2 * border}",
                    border,
                    border,
                    color="white@0.9",
                )
            )
            overlay_x, overlay_y = width - pip_width - pip_margin, pip_margin

        # Shift the overlay's own timeline so it starts *at* its window
        # rather than having already played through while hidden.
        overlay_stream = overlay_stream.filter(
            "setpts", f"PTS-STARTPTS+{window_start:.3f}/TB"
        )

        video_stream = ffmpeg.overlay(
            video_stream,
            overlay_stream,
            x=overlay_x,
            y=overlay_y,
            eof_action="pass",
            enable=f"between(t,{window_start:.3f},{window_end:.3f})",
        )
    return video_stream


def _run_ffmpeg(
    *,
    source_path: str,
    start_time: float,
    duration: float,
    captions: list[tuple[float, float, str]],
    broll_assets: list[BrollAsset],
    output_path: Path,
    tmp_dir: Path,
    framing: str | None = None,
    caption_style: ClipCaptionStyle | None = None,
) -> None:
    """Build and execute the ffmpeg filter graph for one clip.

    Raises FileNotFoundError if the ffmpeg binary is missing, or
    ffmpeg.Error if ffmpeg runs but exits non-zero.
    """

    # Input-level `-ss` seeks fast (and, since ffmpeg 2.1, accurately) so a
    # 2-hour broadcast doesn't have to be decoded up to the clip's start.
    main_input = ffmpeg.input(source_path, ss=start_time, t=duration)

    video_stream = _frame_9x16(
        main_input,
        source_path=source_path,
        start_time=start_time,
        duration=duration,
        framing=framing,
    )
    video_stream = video_stream.filter("fps", fps=settings.RENDER_FPS)
    video_stream = _apply_broll(video_stream, broll_assets, duration, tmp_dir)
    video_stream = _apply_captions(video_stream, captions, tmp_dir, caption_style)

    _encode(video_stream, main_input, output_path, source_path)


def _video_output_kwargs() -> dict[str, Any]:
    """Encoder settings targeting YouTube's recommended Shorts upload spec."""

    fps = settings.RENDER_FPS
    return {
        "vcodec": "libx264",
        "preset": settings.RENDER_PRESET,
        "crf": settings.RENDER_CRF,
        "profile:v": "high",
        "level": "4.2",
        "pix_fmt": "yuv420p",
        "r": fps,
        # 2-second GOP: YouTube's recommended keyframe interval.
        "g": fps * 2,
        "keyint_min": fps,
        "colorspace": "bt709",
        "color_primaries": "bt709",
        "color_trc": "bt709",
        "movflags": "+faststart",
        "max_muxing_queue_size": 1024,
    }


def _audio_output_kwargs() -> dict[str, Any]:
    """Audio settings: stereo AAC-LC at YouTube's recommended bitrate."""

    return {
        "acodec": "aac",
        "audio_bitrate": settings.RENDER_AUDIO_BITRATE,
        "ar": 48000,
        "ac": 2,
    }


def _has_audio_stream(source_path: str) -> bool:
    """Whether `source_path` carries an audio stream ffmpeg can map.

    Asked up front because mapping `[0:a]` on a silent source is a *hard*
    filtergraph error, not a warning: ffmpeg refuses to build the graph and
    the whole export fails. Probing is the only version-proof way to know
    -- the wording of that failure has changed across ffmpeg releases (see
    `_encode`), so matching on stderr alone silently stops working when
    ffmpeg is upgraded.

    On a probe failure this returns True, which keeps the audio path (and
    its stderr fallback) rather than silently dropping sound from a clip
    that has it.
    """

    try:
        probe = ffmpeg.probe(source_path)
    except Exception as exc:
        logger.warning("Could not probe %s for audio streams: %s", source_path, exc)
        return True
    return any(
        stream.get("codec_type") == "audio" for stream in probe.get("streams", [])
    )


def _encode(
    video_stream: Any, main_input: Any, output_path: Path, source_path: str
) -> None:
    """Run the encode, falling back to a video-only output if the source
    has no audio track (rather than failing the whole render)."""

    if not _has_audio_stream(source_path):
        logger.info(
            "render_clip: %s has no audio stream; encoding video-only", source_path
        )
        _encode_video_only(video_stream, output_path)
        return

    audio_stream = main_input.audio
    if "loudnorm" in _available_filters():
        # Normalise to YouTube's -14 LUFS playback target so the clip isn't
        # quietly turned down (or left inaudible) after upload.
        audio_stream = audio_stream.filter(
            "loudnorm", i=settings.RENDER_AUDIO_LUFS, tp=-1.5, lra=11
        )

    try:
        (
            ffmpeg.output(
                video_stream,
                audio_stream,
                str(output_path),
                **_video_output_kwargs(),
                **_audio_output_kwargs(),
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        if _is_missing_audio_error(stderr):
            logger.warning(
                "render_clip: source has no usable audio stream, encoding video-only"
            )
            _encode_video_only(video_stream, output_path)
        else:
            raise


# How ffmpeg reports a missing audio stream, which is worded differently
# across releases: ffmpeg <= 7 fails at the stream map ("Stream map '0:a'
# matches no streams" / "does not contain any stream"), while ffmpeg 8+
# fails a step earlier, binding the filtergraph ("Stream specifier ':a' in
# filtergraph description ... matches no streams"). Matching only the older
# wording made a silent source fail the entire export on a modern build.
_MISSING_AUDIO_MARKERS = (
    "does not contain any stream",
    "matches no streams",
    "Stream map",
)


def _is_missing_audio_error(stderr: str) -> bool:
    """Whether an ffmpeg failure was caused by the source having no audio."""

    return any(marker in stderr for marker in _MISSING_AUDIO_MARKERS)


def _encode_video_only(video_stream: Any, output_path: Path) -> None:
    """Encode without an audio track."""

    (
        ffmpeg.output(video_stream, str(output_path), **_video_output_kwargs())
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def _extract_thumbnail(video_path: Path, duration: float) -> Path | None:
    """Grab a poster frame from the rendered clip.

    Best-effort: a missing thumbnail must never fail an otherwise good
    export, so any error is logged and swallowed.
    """

    thumbnail_path = video_path.with_suffix(".jpg")
    timestamp = min(1.0, max(0.0, duration / 2))
    try:
        (
            ffmpeg.input(str(video_path), ss=timestamp)
            .output(str(thumbnail_path), vframes=1, **{"q:v": 2})
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except Exception as exc:
        logger.warning("Could not extract thumbnail for %s: %s", video_path, exc)
        return None

    if not thumbnail_path.is_file() or thumbnail_path.stat().st_size == 0:
        thumbnail_path.unlink(missing_ok=True)
        return None
    return thumbnail_path


# ---------------------------------------------------------------------------
# B-roll asset resolution
# ---------------------------------------------------------------------------


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
