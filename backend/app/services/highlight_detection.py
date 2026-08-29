"""Heuristic highlight-detection for transcript segments.

MVP implementation: no external ML model or API call. Each segment is
scored using cheap, explainable heuristics:

  - keyword density: presence of words that often signal an engaging,
    quotable, or emotionally charged moment ("secret", "never", "biggest",
    "mistake", ...).
  - duration fit: segments close to a typical short-form clip length score
    higher than ones that are too short (fragmentary) or too long.
  - sentence completeness: segments that read as a complete sentence
    (capitalized start, terminal punctuation) score higher than a mid-
    sentence fragment.

This module's public function signature is intentionally narrow
(`detect_highlights(segments) -> segments`, mutating `is_highlight` /
`highlight_score` in place) so it can later be swapped for a real ML-based
highlight/virality model without touching callers.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.transcript_segment import TranscriptSegment

# Words that often signal an engaging, quotable, or emotionally charged
# moment in spoken content — a crude proxy for "highlight-worthy".
HIGHLIGHT_KEYWORDS: set[str] = {
    "amazing", "incredible", "secret", "never", "always", "best", "worst",
    "biggest", "huge", "shocking", "surprising", "important", "key",
    "mistake", "fail", "failed", "success", "money", "free", "warning",
    "truth", "proven", "guarantee", "love", "hate", "why", "how", "what if",
    "imagine", "stop", "listen", "remember", "crazy", "insane",
    "game changer", "no one", "everyone", "nobody tells you",
}

# Ideal highlight clip length in seconds — short-form platforms (Shorts,
# Reels, TikTok) tend to favor roughly 8-60s segments.
IDEAL_MIN_DURATION = 8.0
IDEAL_MAX_DURATION = 60.0

# Fraction of segments (by score, descending) flagged as highlights.
HIGHLIGHT_FRACTION = 0.2
MIN_HIGHLIGHTS = 1

# Score weights (must sum to 1.0).
_KEYWORD_WEIGHT = 0.5
_DURATION_WEIGHT = 0.3
_COMPLETENESS_WEIGHT = 0.2


def _keyword_score(text: str) -> float:
    lowered = text.lower()
    hits = sum(1 for kw in HIGHLIGHT_KEYWORDS if kw in lowered)
    word_count = max(len(lowered.split()), 1)
    return min(hits / word_count * 10, 1.0)


def _duration_score(start_time: float, end_time: float) -> float:
    duration = end_time - start_time
    if duration <= 0:
        return 0.0
    if IDEAL_MIN_DURATION <= duration <= IDEAL_MAX_DURATION:
        return 1.0
    if duration < IDEAL_MIN_DURATION:
        return duration / IDEAL_MIN_DURATION
    # Longer than ideal: decay towards 0 the further past the max it runs.
    return max(0.0, 1.0 - (duration - IDEAL_MAX_DURATION) / IDEAL_MAX_DURATION)


def _completeness_score(text: str) -> float:
    stripped = text.strip()
    if not stripped:
        return 0.0
    ends_clean = bool(re.search(r"[.!?]$", stripped))
    starts_capitalized = stripped[0].isupper()
    return (0.5 if ends_clean else 0.0) + (0.5 if starts_capitalized else 0.0)


def _score_segment(segment: TranscriptSegment) -> float:
    keyword = _keyword_score(segment.text)
    duration = _duration_score(segment.start_time, segment.end_time)
    completeness = _completeness_score(segment.text)
    score = (
        _KEYWORD_WEIGHT * keyword
        + _DURATION_WEIGHT * duration
        + _COMPLETENESS_WEIGHT * completeness
    )
    return round(score, 4)


def calculate_target_shorts_count(total_duration_seconds: float) -> int:
    """Calculate the ideal number of shorts based on total video duration.

    Scaling rule:
      - <= 60s: 1 short
      - <= 3 min (180s): 2 shorts
      - <= 6 min (360s): 3 shorts
      - <= 10 min (600s): 4-5 shorts
      - <= 20 min (1200s): 6-7 shorts
      - <= 30 min (1800s): 8-10 shorts
      - <= 60 min (3600s): 12-15 shorts
      - > 60 min: ~1 short per 4 minutes (up to 25)
    """
    if total_duration_seconds <= 60.0:
        return 1
    elif total_duration_seconds <= 180.0:
        return 2
    elif total_duration_seconds <= 360.0:
        return 3
    elif total_duration_seconds <= 600.0:
        return 4
    elif total_duration_seconds <= 1200.0:
        return 6
    elif total_duration_seconds <= 1800.0:
        return 8
    elif total_duration_seconds <= 3600.0:
        return 12
    else:
        return min(25, max(12, int(total_duration_seconds // 240)))


def detect_highlights(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Score transcript segments and flag highlights based on video duration.

    Mutates every segment in place, setting:
      - `highlight_score`: a 0.0-1.0 heuristic score.
      - `is_highlight`: True for the top-scoring segments proportional to
        the video duration, distributed across the timeline.

    Does not commit/persist changes — callers own the DB session and
    transaction. Returns the same list (now scored) for convenience.
    """
    if not segments:
        return segments

    for segment in segments:
        segment.highlight_score = _score_segment(segment)
        segment.is_highlight = False

    min_time = min(s.start_time for s in segments)
    total_duration = max(s.end_time for s in segments) - min_time
    target_count = calculate_target_shorts_count(total_duration)

    # If segment count is small, clamp target count
    target_count = max(MIN_HIGHLIGHTS, min(target_count, len(segments)))

    # Sort segments by highlight_score descending
    ranked = sorted(segments, key=lambda s: s.highlight_score or 0.0, reverse=True)

    # Bucket segments temporally so highlights are distributed across the entire video
    # from the beginning to the very end.
    if target_count > 1 and len(segments) >= target_count * 2:
        bucket_size = total_duration / target_count

        for b in range(target_count):
            b_start = min_time + b * bucket_size
            b_end = min_time + (b + 1) * bucket_size
            bucket_segs = [
                s for s in segments
                if (s.start_time >= b_start and s.start_time < b_end) or (s.end_time > b_start and s.end_time <= b_end)
            ]
            if bucket_segs:
                best_in_bucket = max(bucket_segs, key=lambda s: s.highlight_score or 0.0)
                best_in_bucket.is_highlight = True

        # Fill remaining slots with highest overall scores if any bucket was empty
        current_count = sum(1 for s in segments if s.is_highlight)
        if current_count < target_count:
            for s in ranked:
                if not s.is_highlight:
                    s.is_highlight = True
                    current_count += 1
                    if current_count >= target_count:
                        break
    else:
        for segment in ranked[:target_count]:
            segment.is_highlight = True

    return segments
