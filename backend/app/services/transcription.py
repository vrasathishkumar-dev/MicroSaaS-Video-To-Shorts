"""Video transcription service.

Calls an external Whisper-compatible transcription API to produce
timestamped transcript segments for a video/audio file.

No concrete transcription provider was specified for this project, so this
implementation targets the OpenAI-compatible `audio/transcriptions` REST
shape as a reasonable default:

    POST {TRANSCRIPTION_API_URL}
    Headers: Authorization: Bearer <settings.TRANSCRIPTION_API_KEY>
    Body (multipart/form-data):
        file=<binary>, model="whisper-1", response_format="verbose_json"

`response_format="verbose_json"` is required to get back segment-level
timestamps (a `segments` array of {start, end, text, ...}) rather than just
a flat transcript string. This shape is also implemented by several
self-hosted / open-source Whisper-compatible servers, so swapping providers
should mostly mean changing TRANSCRIPTION_API_URL. If a provider with a
genuinely different response shape is adopted later, only the response
parsing below needs to change — the public `transcribe_video()` signature
should stay stable for callers.
"""

from __future__ import annotations

import asyncio
import logging
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


def _generate_fallback_transcript(file_path: Path) -> list[dict]:
    """Generate realistic transcript segments for the ENTIRE duration of the video."""
    duration = 60.0
    try:
        import ffmpeg
        probe = ffmpeg.probe(str(file_path))
        format_info = probe.get("format", {})
        duration = float(format_info.get("duration", 60.0))
    except Exception:
        pass

    # Ensure duration is a valid positive value
    duration = max(10.0, duration)

    topic_sentences = [
        "Welcome everyone! Today we are exploring the biggest game-changing secrets to mastering this workflow.",
        "Here is the single most important mistake that 99% of people make when starting out.",
        "If you want to achieve massive success, you must master the fundamental principles first.",
        "Nobody tells you how simple this actually is once you break down the core system step by step.",
        "Imagine if you could save dozens of hours every single week by implementing this one key technique.",
        "Let's dive into the core architecture and see exactly how high-performing teams execute on this.",
        "The surprising truth is that most strategies fail because they ignore this critical detail.",
        "When you look at the top creators and industry leaders, they all follow this exact blueprint.",
        "This incredible insight completely changes the way you approach productivity and content creation.",
        "Let's analyze what makes this approach so remarkably effective compared to traditional methods.",
        "Here is a proven framework that will help you accelerate your growth without burning out.",
        "Pay close attention to this next point because it is the linchpin of the whole operation.",
        "Many people think this requires massive resources, but you can start right now with zero overhead.",
        "By focusing on high-leverage activities, you multiply your results with half the effort.",
        "Notice how each component connects seamlessly to deliver maximum engagement and clarity.",
        "This is why consistency and iterative improvement always outperform overnight hype.",
        "Let's review the key takeaways and actionable steps you can implement today.",
        "Thank you so much for watching! If you found this valuable, be sure to like and subscribe for more insights.",
    ]

    segments = []
    current_time = 0.0
    index = 0

    while current_time < duration:
        sentence = topic_sentences[index % len(topic_sentences)]
        word_count = len(sentence.split())
        seg_duration = min(max(word_count * 0.45, 5.0), 12.0)
        end_time = min(round(current_time + seg_duration, 2), duration)

        segments.append({
            "start_time": round(current_time, 2),
            "end_time": end_time,
            "text": sentence,
        })
        current_time = end_time
        index += 1
        if end_time >= duration:
            break

    return segments or [{"start_time": 0.0, "end_time": min(duration, 10.0), "text": "Highlight segment for clip generation."}]


import tempfile

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


async def transcribe_video(file_path: str) -> list[dict]:
    """Transcribe the video/audio file at `file_path` into timestamped segments.

    Returns a list of segments, each shaped as:
        {"start_time": float, "end_time": float, "text": str}
    in chronological order.

    Uses OpenAI Whisper when TRANSCRIPTION_API_KEY is set, or provides
    development transcript segments when testing locally without a key.

    In production (settings.ENVIRONMENT == "production"), a missing key
    raises instead of silently falling back -- the fallback transcript is
    generic placeholder text unrelated to the actual video, so highlight
    detection and every downstream clip would be based on fabricated
    "highlights" rather than the user's real content, with no visible error.
    """
    path = Path(file_path)
    if not path.exists():
        raise TranscriptionError(f"File not found for transcription: {file_path}")

    if not settings.TRANSCRIPTION_API_KEY:
        if settings.ENVIRONMENT == "production":
            raise TranscriptionError(
                "TRANSCRIPTION_API_KEY is not configured. Real transcription is "
                "required in production so highlights reflect the actual video -- "
                "set TRANSCRIPTION_API_KEY in the environment."
            )
        logger.warning(
            "TRANSCRIPTION_API_KEY is not configured. Using development transcript segments for %s. Set TRANSCRIPTION_API_KEY in .env for OpenAI Whisper transcription.",
            file_path,
        )
        return _generate_fallback_transcript(path)

    headers = {"Authorization": f"Bearer {settings.TRANSCRIPTION_API_KEY}"}
    data = {"model": TRANSCRIPTION_MODEL, "response_format": "verbose_json"}

    temp_audio_file = Path(tempfile.mktemp(suffix=".mp3"))
    try:
        has_audio = await asyncio.to_thread(_extract_audio_for_whisper, path, temp_audio_file)
        upload_path = temp_audio_file if has_audio else path
        upload_filename = "audio.mp3" if has_audio else path.name
        upload_mime = "audio/mpeg" if has_audio else "application/octet-stream"

        file_bytes = await asyncio.to_thread(upload_path.read_bytes)
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
        if settings.ENVIRONMENT != "production":
            logger.warning(
                "Transcription API key invalid or failed (%s). Falling back to development transcript generator.",
                exc.response.status_code,
            )
            return _generate_fallback_transcript(path)
        raise TranscriptionError(
            f"Transcription API error ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Transcription API request failed for %s: %s", file_path, exc)
        if settings.ENVIRONMENT != "production":
            logger.warning(
                "Transcription network request failed (%s). Falling back to development transcript generator.",
                exc,
            )
            return _generate_fallback_transcript(path)
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
