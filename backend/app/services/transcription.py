"""Video transcription: turning what is said into timestamped segments.

Everything downstream is built on this. Highlight detection reads it to
decide which moments become shorts, the titles come from it, the captions
burned into the export are it, and B-roll is searched from its words. A
transcript that isn't what the video actually says produces shorts about
nothing, with no visible error -- which is why this module has no
"placeholder transcript" path any more. It transcribes, or it fails.

Two backends, chosen by `TRANSCRIPTION_BACKEND`:

- **local** (`faster-whisper`): runs Whisper on this machine. No API key,
  no per-minute cost, and roughly 10x faster than realtime on a laptop CPU
  with the `base` model. The model downloads once on first use.
- **api**: an OpenAI-compatible `audio/transcriptions` endpoint, using
  `response_format="verbose_json"` for segment-level timestamps. Several
  self-hosted Whisper servers implement the same shape, so swapping
  providers should mostly mean changing TRANSCRIPTION_API_URL.

If a sidecar `.vtt` subtitle track was downloaded alongside a YouTube video
via `yt-dlp` and the configured Whisper backend is unavailable, the real
YouTube timed captions are parsed into segments as a fallback.

`auto` (the default) takes the API when a key is configured and local
otherwise, so a fresh checkout transcribes for real with nothing to set up.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TRANSCRIPTION_API_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIPTION_MODEL = "whisper-1"
REQUEST_TIMEOUT_SECONDS = 600.0  # transcription of long videos can take a while

_VTT_CUE_RE = re.compile(
    r"(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})"
)
_VTT_TAG_RE = re.compile(r"<[^>]+>")


class TranscriptionError(Exception):
    """Raised when the transcription API call fails or returns unusable data.

    Callers (the video processing pipeline) are responsible for catching
    this and marking the owning VideoProject as failed with an appropriate
    error_message — this service does not touch the database.
    """


def _extract_audio_for_whisper(video_path: Path, output_audio_path: Path) -> bool:
    """Extract 16kHz mono audio track to guarantee payload stays well under OpenAI's 25MB limit."""
    try:
        import ffmpeg
        (
            ffmpeg.input(str(video_path))
            .output(str(output_audio_path), acodec="libmp3lame", ar=16000, ac=1, ab="48k", vn=None)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_audio_path.exists() and output_audio_path.stat().st_size > 0
    except Exception as exc:
        logger.warning("Could not extract audio via ffmpeg: %s", exc)
        return False


def parse_vtt_subtitles(vtt_path: Path) -> list[dict]:
    """Parse a WebVTT subtitle file into clean, non-overlapping transcript segments."""
    if not vtt_path.is_file():
        return []
    raw_text = vtt_path.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\r?\n\r?\n+", raw_text)
    cues: list[dict] = []
    last_text = ""

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        match = None
        cue_idx = 0
        for idx, line in enumerate(lines):
            m = _VTT_CUE_RE.search(line)
            if m:
                match = m
                cue_idx = idx
                break
        if match is None:
            continue

        h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()
        start = (
            int(h1 or 0) * 3600
            + int(m1) * 60
            + int(s1)
            + int(ms1) / 1000.0
        )
        end = (
            int(h2 or 0) * 3600
            + int(m2) * 60
            + int(s2)
            + int(ms2) / 1000.0
        )
        if end <= start:
            continue

        text_lines = lines[cue_idx + 1 :]
        clean_lines: list[str] = []
        for tline in text_lines:
            cleaned = _VTT_TAG_RE.sub("", tline).strip()
            if cleaned and cleaned != last_text:
                clean_lines.append(cleaned)
                last_text = cleaned
        text = " ".join(clean_lines).strip()
        if not text:
            continue

        # Merge micro-cues from rolling YouTube auto-captions into 3-8s spoken phrases
        if (
            cues
            and start - cues[-1]["end_time"] <= 0.6
            and (end - cues[-1]["start_time"]) <= 7.5
            and not str(cues[-1]["text"]).endswith((".", "!", "?"))
        ):
            cues[-1]["end_time"] = round(end, 2)
            cues[-1]["text"] = f"{cues[-1]['text']} {text}".strip()
        else:
            cues.append(
                {
                    "start_time": round(start, 2),
                    "end_time": round(end, 2),
                    "text": text,
                }
            )
    return cues


def _find_sidecar_vtt(video_path: Path) -> Path | None:
    """Locate any yt-dlp downloaded `.vtt` subtitle file matching `video_path`'s stem."""
    parent = video_path.parent
    if not parent.is_dir():
        return None
    candidates = sorted(parent.glob(f"{video_path.stem}*.vtt"))
    return candidates[0] if candidates else None


@lru_cache(maxsize=2)
def _local_model(model_size: str, device: str, compute_type: str):  # type: ignore[no-untyped-def]
    """Load a faster-whisper model, once per process.

    Loading costs seconds and hundreds of megabytes, and a worker
    transcribes video after video, so the model is kept rather than rebuilt
    per job. Cached on the settings that define it, so changing them in a
    long-running process still takes effect.
    """

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - exercised via the caller
        raise TranscriptionError(
            "Local transcription needs faster-whisper: `pip install "
            "faster-whisper` (or set TRANSCRIPTION_API_KEY to use the "
            "hosted Whisper API instead)."
        ) from exc

    logger.info(
        "Loading local Whisper model %r (device=%s, compute_type=%s); the "
        "first run downloads it",
        model_size,
        device,
        compute_type,
    )
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _transcribe_locally(audio_path: Path) -> list[dict]:
    """Transcribe with faster-whisper on this machine.

    Voice-activity filtering is on: it drops music, applause and silence
    instead of hallucinating words over them, which matters because every
    segment here is a candidate for becoming a short.
    """

    model = _local_model(
        settings.WHISPER_MODEL, settings.WHISPER_DEVICE, settings.WHISPER_COMPUTE_TYPE
    )
    segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
        language=settings.WHISPER_LANGUAGE or None,
    )

    transcript = [
        {
            "start_time": float(segment.start),
            "end_time": float(segment.end),
            "text": segment.text.strip(),
        }
        for segment in segments
        if segment.text and segment.text.strip()
    ]

    logger.info(
        "Local Whisper transcribed %.0fs of %s speech into %d segments",
        info.duration,
        info.language,
        len(transcript),
    )
    if not transcript:
        raise TranscriptionError(
            "No speech was found in this video, so there is nothing to make "
            "shorts from."
        )
    return transcript


def _backend() -> str:
    """Which transcription backend to use for this run."""

    configured = settings.TRANSCRIPTION_BACKEND.strip().lower()
    if configured in {"local", "api"}:
        return configured
    return "api" if settings.TRANSCRIPTION_API_KEY else "local"


async def transcribe_video(file_path: str) -> list[dict]:
    """Transcribe the video/audio file at `file_path` into timestamped segments.

    Returns a list of segments, each shaped as:
        {"start_time": float, "end_time": float, "text": str}
    in chronological order.

    Runs local Whisper or the hosted API depending on
    `TRANSCRIPTION_BACKEND` (see the module docstring). If a sidecar `.vtt`
    subtitle track exists next to `file_path` (downloaded by `yt-dlp`) and
    the configured Whisper backend raises a `TranscriptionError`, falls back
    to the real timed YouTube subtitles.

    Raises:
        TranscriptionError: the file is missing, no backend is usable, the
            provider failed, or there is no speech in the video.
    """

    path = Path(file_path)
    if not path.exists():
        raise TranscriptionError(f"File not found for transcription: {file_path}")

    sidecar_vtt = _find_sidecar_vtt(path)

    backend = _backend()
    temp_audio_file = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        has_audio = await asyncio.to_thread(
            _extract_audio_for_whisper, path, temp_audio_file
        )
        source_path = temp_audio_file if has_audio else path

        if backend == "local":
            try:
                # Whisper is CPU-bound and blocks; keep the event loop free.
                return await asyncio.to_thread(_transcribe_locally, source_path)
            except TranscriptionError:
                if sidecar_vtt is not None:
                    vtt_segments = parse_vtt_subtitles(sidecar_vtt)
                    if vtt_segments:
                        logger.info(
                            "Using YouTube sidecar VTT captions (%d segments) for %s",
                            len(vtt_segments),
                            file_path,
                        )
                        return vtt_segments
                raise

        headers = {"Authorization": f"Bearer {settings.TRANSCRIPTION_API_KEY}"}
        data = {"model": TRANSCRIPTION_MODEL, "response_format": "verbose_json"}
        upload_filename = "audio.mp3" if has_audio else path.name
        upload_mime = "audio/mpeg" if has_audio else "application/octet-stream"

        file_bytes = await asyncio.to_thread(source_path.read_bytes)
        files = {"file": (upload_filename, file_bytes, upload_mime)}
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                TRANSCRIPTION_API_URL, headers=headers, data=data, files=files
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if sidecar_vtt is not None:
            vtt_segments = parse_vtt_subtitles(sidecar_vtt)
            if vtt_segments:
                return vtt_segments
        logger.error(
            "Transcription API returned %s for %s: %s",
            exc.response.status_code,
            file_path,
            exc.response.text,
        )
        raise TranscriptionError(
            f"Transcription API error ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        if sidecar_vtt is not None:
            vtt_segments = parse_vtt_subtitles(sidecar_vtt)
            if vtt_segments:
                return vtt_segments
        logger.error("Transcription API request failed for %s: %s", file_path, exc)
        raise TranscriptionError("Transcription API request failed") from exc
    finally:
        temp_audio_file.unlink(missing_ok=True)

    try:
        payload = response.json()
        raw_segments = payload["segments"]
        segments = [
            {
                "start_time": float(seg["start"]),
                "end_time": float(seg["end"]),
                "text": str(seg["text"]).strip(),
            }
            for seg in raw_segments
        ]
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("Malformed transcription response for %s: %s", file_path, exc)
        raise TranscriptionError("Malformed transcription API response") from exc

    if not segments:
        raise TranscriptionError("Transcription API returned no segments")

    return segments
