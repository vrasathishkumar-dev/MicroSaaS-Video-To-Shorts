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

`auto` (the default) takes the API when a key is configured and local
otherwise, so a fresh checkout transcribes for real with nothing to set up.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TRANSCRIPTION_API_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIPTION_MODEL = "whisper-1"
REQUEST_TIMEOUT_SECONDS = 600.0  # transcription of long videos can take a while


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
    `TRANSCRIPTION_BACKEND` (see the module docstring). Raises rather than
    inventing a transcript: everything downstream -- which moments become
    shorts, their titles, their captions -- is built on what comes back
    from here, so a wrong transcript is worse than a failed job.

    Raises:
        TranscriptionError: the file is missing, no backend is usable, the
            provider failed, or there is no speech in the video.
    """

    path = Path(file_path)
    if not path.exists():
        raise TranscriptionError(f"File not found for transcription: {file_path}")

    backend = _backend()
    temp_audio_file = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        has_audio = await asyncio.to_thread(
            _extract_audio_for_whisper, path, temp_audio_file
        )
        source_path = temp_audio_file if has_audio else path

        if backend == "local":
            # Whisper is CPU-bound and blocks; keep the event loop free.
            return await asyncio.to_thread(_transcribe_locally, source_path)

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
