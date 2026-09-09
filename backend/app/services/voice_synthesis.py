"""Voice synthesis (Text-to-Speech) for AI-generated Short-form videos.

Produces high-quality narration audio and timestamped sentence/phrase events
so that:
1. The video has a real, human-like voiceover track (via edge-tts / OpenAI / say).
2. The video duration matches the spoken narration (~25–35 seconds).
3. Captions are timed and synced with what the voice is saying.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Default high-quality voices
DEFAULT_NEURAL_VOICE = "en-US-ChristopherNeural"  # Deep, documentary-style narrator
FALLBACK_NEURAL_VOICES = [
    "en-US-GuyNeural",
    "en-US-JennyNeural",
    "en-GB-RyanNeural",
]


def get_audio_duration(file_path: Path) -> float:
    """Read exact duration of an audio file in seconds via ffprobe."""
    try:
        res = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        return float(res.stdout.strip())
    except Exception as exc:
        logger.warning("Could not probe audio duration for %s: %s", file_path, exc)
        return 30.0


async def synthesize_speech(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_NEURAL_VOICE,
) -> tuple[Path, list[tuple[float, float, str]], float]:
    """Generate audio voiceover and timestamped subtitle events for `text`.

    Returns:
        `(output_path, events, total_duration)`
        where `events` is a list of `(start_time, end_time, phrase_text)`
    """
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Cannot synthesize empty text")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Try edge-tts (free, fast, studio-quality neural voice)
    try:
        events, dur = await _synthesize_edge_tts(clean_text, output_path, voice)
        if dur > 0 and output_path.exists() and output_path.stat().st_size > 500:
            logger.info("edge-tts synthesis succeeded: %s (%.2fs)", output_path, dur)
            return output_path, events, dur
    except Exception as exc:
        logger.warning("edge-tts synthesis failed: %s; trying fallback", exc)

    # 2. Try OpenAI TTS if OPENAI_API_KEY is configured
    if getattr(settings, "OPENAI_API_KEY", None):
        try:
            events, dur = await _synthesize_openai_tts(clean_text, output_path)
            if dur > 0 and output_path.exists():
                logger.info("OpenAI TTS synthesis succeeded: %s (%.2fs)", output_path, dur)
                return output_path, events, dur
        except Exception as exc:
            logger.warning("OpenAI TTS synthesis failed: %s", exc)

    # 3. Try macOS /usr/bin/say fallback
    try:
        events, dur = _synthesize_macos_say(clean_text, output_path)
        if dur > 0 and output_path.exists():
            logger.info("macOS say synthesis succeeded: %s (%.2fs)", output_path, dur)
            return output_path, events, dur
    except Exception as exc:
        logger.warning("macOS say fallback failed: %s", exc)

    # 4. Final silent fallback if no TTS engine is available
    logger.error("All TTS engines failed; creating silent fallback")
    return _create_silent_fallback(clean_text, output_path)


async def _synthesize_edge_tts(
    text: str,
    output_path: Path,
    voice: str,
) -> tuple[list[tuple[float, float, str]], float]:
    """Synthesize with edge-tts and capture SentenceBoundary timestamps."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    events: list[tuple[float, float, str]] = []

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                start = chunk["offset"] / 10_000_000.0
                dur = chunk["duration"] / 10_000_000.0
                sentence_text = chunk["text"].strip()
                if sentence_text:
                    events.append((round(start, 2), round(start + dur, 2), sentence_text))

    total_duration = get_audio_duration(output_path)

    # Break long sentences into punchy chunks (4–7 words each) with proportional timings
    refined_events = _break_into_punchy_subtitles(events, total_duration, text)
    return refined_events, total_duration


async def _synthesize_openai_tts(
    text: str,
    output_path: Path,
) -> tuple[list[tuple[float, float, str]], float]:
    """Call OpenAI Audio Speech API."""
    import openai

    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text,
    )
    with open(output_path, "wb") as f:
        f.write(response.content)

    total_duration = get_audio_duration(output_path)
    events = _estimate_sentence_timings(text, total_duration)
    return events, total_duration


def _synthesize_macos_say(
    text: str,
    output_path: Path,
) -> tuple[list[tuple[float, float, str]], float]:
    """Call macOS /usr/bin/say and convert to mp3."""
    aiff_path = output_path.with_suffix(".aiff")
    subprocess.run(["/usr/bin/say", "-v", "Alex", "-o", str(aiff_path), text], check=True, timeout=60)

    # Convert to mp3
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(aiff_path),
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    aiff_path.unlink(missing_ok=True)

    total_duration = get_audio_duration(output_path)
    events = _estimate_sentence_timings(text, total_duration)
    return events, total_duration


def _create_silent_fallback(
    text: str,
    output_path: Path,
) -> tuple[Path, list[tuple[float, float, str]], float]:
    """Create a silent audio file of ~30 seconds if TTS completely fails."""
    duration = 30.0
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-c:a", "libmp3lame", "-b:a", "128k",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )
    events = _estimate_sentence_timings(text, duration)
    return output_path, events, duration


def _estimate_sentence_timings(text: str, total_duration: float) -> list[tuple[float, float, str]]:
    """Estimate start/end times proportionally by sentence length."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text]

    total_chars = sum(len(s) for s in sentences)
    if total_chars == 0:
        return [(0.0, total_duration, text)]

    events: list[tuple[float, float, str]] = []
    current_time = 0.0
    for s in sentences:
        share = total_duration * (len(s) / total_chars)
        end_time = min(total_duration, current_time + share)
        events.append((round(current_time, 2), round(end_time, 2), s))
        current_time = end_time

    return _break_into_punchy_subtitles(events, total_duration, text)


def _break_into_punchy_subtitles(
    sentence_events: list[tuple[float, float, str]],
    total_duration: float,
    fallback_text: str,
) -> list[tuple[float, float, str]]:
    """Break sentences into 4-7 word phrases for mobile short-form legibility.

    If a sentence is 15 words long, showing it all at once fills the screen.
    Breaking it into 2-3 shorter phrases that change as spoken makes captions
    look professional like TikTok / YouTube Shorts creators.
    """
    if not sentence_events:
        return [(0.0, total_duration, fallback_text)]

    punchy_events: list[tuple[float, float, str]] = []

    for start, end, sentence in sentence_events:
        words = sentence.split()
        if len(words) <= 7:
            punchy_events.append((start, end, sentence))
            continue

        # Split into chunks of ~5-6 words
        chunk_size = 5
        chunks = [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]
        sent_dur = max(0.5, end - start)
        total_words = len(words)

        cur_t = start
        for c in chunks:
            c_words = len(c.split())
            share = sent_dur * (c_words / total_words)
            c_end = min(end, cur_t + share)
            punchy_events.append((round(cur_t, 2), round(c_end, 2), c))
            cur_t = c_end

    return punchy_events


def synthesize_speech_sync(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_NEURAL_VOICE,
) -> tuple[Path, list[tuple[float, float, str]], float]:
    """Synchronous wrapper for synthesize_speech."""
    return asyncio.run(synthesize_speech(text, output_path, voice))
