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


def detect_highlights(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Score transcript segments and flag the top-scoring ones as highlights.

    Mutates every segment in place, setting:
      - `highlight_score`: a 0.0-1.0 heuristic score.
      - `is_highlight`: True for the top HIGHLIGHT_FRACTION of segments by
        score (at least MIN_HIGHLIGHTS when the list is non-empty), False
        otherwise.

    Does not commit/persist changes — callers own the DB session and
    transaction. Returns the same list (now scored) for convenience.
    """
    if not segments:
        return segments

    for segment in segments:
        segment.highlight_score = _score_segment(segment)
        segment.is_highlight = False

    ranked = sorted(segments, key=lambda s: s.highlight_score or 0.0, reverse=True)
    highlight_count = max(MIN_HIGHLIGHTS, round(len(segments) * HIGHLIGHT_FRACTION))
    for segment in ranked[:highlight_count]:
        segment.is_highlight = True

    return segments
