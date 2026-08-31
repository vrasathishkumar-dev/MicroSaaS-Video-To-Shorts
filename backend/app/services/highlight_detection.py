"""Picking the moments worth turning into shorts.

No ML model or API call: cheap, explainable heuristics over the real
transcript. What changed the thinking here is that a short is a *window*,
not a sentence. Whisper hands back segments a second or two long, so
scoring them individually asks the wrong question -- "is this sentence
good?" -- when the one that matters is "if a short started here, would
anyone watch it?".

So each segment is scored as the opening of the ~40 seconds that follow it:

  - **hook**: how the window opens. A question, a claim, a number, a
    contradiction -- the first two seconds decide whether anyone stays, so
    this carries the most weight.
  - **payoff**: whether the rest of the window has substance -- the
    keywords that signal a point being made rather than small talk.
  - **density**: words per second across the window. Applause, music, and
    long pauses read as low density; a made point reads as normal speech.
  - **completeness**: does the window start at the beginning of a thought
    rather than halfway through one.
  - **filler penalty**: greetings, thanks, and audience noise are what a
    talk show is full of and what nobody clips.

`detect_highlights(segments) -> segments` still marks `is_highlight` /
`highlight_score` in place, so this stays swappable for a real virality
model without touching callers.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.transcript_segment import TranscriptSegment

# Roughly what a generated short covers. Scoring looks this far past each
# segment, because that is the material a viewer would actually get.
SHORT_WINDOW_SECONDS = 40.0

# Words that signal a point being made rather than small talk -- a crude
# proxy for "there is something here worth clipping".
HIGHLIGHT_KEYWORDS: set[str] = {
    "amazing", "incredible", "secret", "never", "always", "best", "worst",
    "biggest", "huge", "shocking", "surprising", "important", "key",
    "mistake", "fail", "failed", "success", "money", "free", "warning",
    "truth", "proven", "guarantee", "love", "hate", "why", "how", "what if",
    "imagine", "stop", "listen", "remember", "crazy", "insane",
    "game changer", "no one", "everyone", "nobody tells you",
    "realized", "learned", "changed my", "the reason", "the problem",
    "the thing is", "difference", "actually", "honestly", "literally",
}

# How a clip that holds attention tends to open. Matched against the first
# segment of the window only: these earn their weight by being the first
# thing a scroller hears.
_HOOK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\?\s*$",                                   # a question
        r"^(what|why|how|when|who|which|where)\b",   # ...or one being asked
        r"\b(here'?s|this is) (the|why|what|how)\b",
        r"\bthe (truth|secret|reason|problem|thing|trick|point|difference)\b",
        r"\b(nobody|no one|most people|everyone) (tells|knows|thinks|does)\b",
        r"\bi (never|always|used to|didn'?t|couldn'?t|realized|learned)\b",
        r"\b(biggest|worst|best|first|only|hardest|craziest)\b",
        r"\b(you (should|need to|have to|can)|if you)\b",
        r"\b\d+([.,]\d+)?\s*(things|ways|reasons|years|minutes|percent|%|x|k|million|dollars)\b",
        r"\$\s*\d",
        r"\b(but|actually|honestly|the thing is|turns out)\b",
    )
)

# What a room full of people sounds like between the parts worth clipping.
_FILLER_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bthank you\b",
        r"\bthanks (so much|again|for)\b",
        r"\bwelcome (back|to the show|everyone)\b",
        r"\b(please welcome|ladies and gentlemen)\b",
        r"\b(applause|laughter|music|cheering)\b",
        r"^\s*[\[\(].*[\]\)]\s*$",   # [Applause], (Music)
        r"\b(hi|hey|hello) (everybody|everyone|guys)\b",
        r"\b(ladies|gentlemen|folks)\b",
        r"\bgood (morning|evening|to see you)\b",
    )
)

# The words that carry a point, as opposed to the ones that carry a
# conversation. Deliberately narrower than HIGHLIGHT_KEYWORDS: "why" and
# "how" appear in every other sentence of an interview, so counting them
# as payoff makes chit-chat look like insight.
INSIGHT_KEYWORDS: set[str] = {
    "realized", "realised", "learned", "mistake", "truth", "reason",
    "secret", "biggest", "worst", "best", "never", "always", "changed",
    "difference", "important", "surprising", "shocking", "failed",
    "advice", "lesson", "problem", "turns out", "the thing is",
    "what happened", "the first time", "years", "nobody",
}

# Normal conversational speech, in words per second. Used to normalise the
# density score: much below this is a pause, applause or music.
_SPEECH_WORDS_PER_SECOND = 2.6

# A clip has to open with a sentence, not a syllable. "Why?" matches every
# hook pattern going and makes a terrible opening line, so an opener this
# short earns no hook credit at all.
_MIN_HOOK_WORDS = 5

# Openers that are visibly the middle of a thought. Starting a short here
# means opening on "...but I couldn't figure out how", which reads as a
# broken clip however good what follows is.
_CONTINUATION_PATTERN = re.compile(
    r"^\s*(and|but|so|because|which|that|then|or|also|anyway|though)\b",
    re.IGNORECASE,
)

# Uninterrupted narration comes in long segments; banter comes in scraps.
# Mean segment length, in seconds, that counts as someone telling a story.
_STORY_SEGMENT_SECONDS = 3.0

# Score weights (sum to 1.0 before penalties are subtracted).
_HOOK_WEIGHT = 0.30
_PAYOFF_WEIGHT = 0.25
_DENSITY_WEIGHT = 0.20
_STORY_WEIGHT = 0.15
_COMPLETENESS_WEIGHT = 0.10
# How much a window full of greetings and applause can lose.
_MAX_FILLER_PENALTY = 0.45
# ...and how much opening mid-thought costs.
_MAX_CONTINUATION_PENALTY = 0.30

# Fraction of segments (by score, descending) flagged as highlights.
HIGHLIGHT_FRACTION = 0.2
MIN_HIGHLIGHTS = 1

# Kept for callers and tests that reason about clip length bounds.
IDEAL_MIN_DURATION = 8.0
IDEAL_MAX_DURATION = 60.0


def hook_score(text: str) -> float:
    """How strongly this line opens a short. 0-1.

    Public because clip titles are chosen the same way: the line that would
    make the best opening also makes the best title.
    """

    stripped = text.strip()
    if len(stripped.split()) < _MIN_HOOK_WORDS:
        # "Why?" is not a hook, it is half of someone else's sentence.
        return 0.0
    hits = sum(1 for pattern in _HOOK_PATTERNS if pattern.search(stripped))
    # Two independent signals is already a strong opener; more is noise.
    return min(hits / 2.0, 1.0)


def _payoff_score(text: str) -> float:
    """Whether the window says something, by insight-word density. 0-1."""

    lowered = text.lower()
    hits = sum(1 for keyword in INSIGHT_KEYWORDS if keyword in lowered)
    words = max(len(lowered.split()), 1)
    # ~1 insight word per 25 spoken words is a stretch making a point.
    return min(hits / words * 25.0, 1.0)


def _continuation_penalty(text: str) -> float:
    """Whether this opens mid-thought rather than at the start of one."""

    stripped = text.strip()
    if not stripped:
        return 1.0
    if _CONTINUATION_PATTERN.match(stripped):
        return 1.0
    return 0.0 if stripped[0].isupper() else 1.0


def _story_score(window: list[TranscriptSegment]) -> float:
    """Whether one person is telling something, or a room is trading lines.

    Whisper breaks on pauses, so an uninterrupted stretch of narration
    arrives as long segments and rapid back-and-forth arrives as scraps.
    """

    if not window:
        return 0.0
    lengths = [
        segment.end_time - segment.start_time
        for segment in window
        if segment.end_time > segment.start_time
    ]
    if not lengths:
        return 0.0
    mean_length = sum(lengths) / len(lengths)
    return min(mean_length / _STORY_SEGMENT_SECONDS, 1.0)


def _density_score(text: str, duration: float) -> float:
    """Words per second, normalised. Silence and applause score low."""

    if duration <= 0:
        return 0.0
    words_per_second = len(text.split()) / duration
    return min(words_per_second / _SPEECH_WORDS_PER_SECOND, 1.0)


def _completeness_score(text: str) -> float:
    """Whether this reads as the start of a thought rather than the middle."""

    stripped = text.strip()
    if not stripped:
        return 0.0
    ends_clean = bool(re.search(r"[.!?]$", stripped))
    starts_capitalized = stripped[0].isupper()
    return (0.5 if ends_clean else 0.0) + (0.5 if starts_capitalized else 0.0)


def _filler_penalty(text: str) -> float:
    """How much of this window is the noise between the good parts. 0-1."""

    stripped = text.strip()
    if not stripped:
        return 1.0
    hits = sum(1 for pattern in _FILLER_PATTERNS if pattern.search(stripped))
    words = len(stripped.split())
    if words < 6:
        # Barely anything said: an interjection, not a moment.
        return 1.0
    return min(hits / 3.0, 1.0)


def _window_from(
    segments: list[TranscriptSegment], index: int
) -> list[TranscriptSegment]:
    """The segments the short starting at `index` would cover."""

    limit = segments[index].start_time + SHORT_WINDOW_SECONDS
    window = []
    for segment in segments[index:]:
        if segment.start_time >= limit:
            break
        window.append(segment)
    return window


def _score_segment(segments: list[TranscriptSegment], index: int) -> float:
    """Score the short that would open at `segments[index]`."""

    opening = segments[index]
    window = _window_from(segments, index)
    window_text = " ".join(segment.text.strip() for segment in window)
    window_duration = max(window[-1].end_time - opening.start_time, 0.0)

    score = (
        _HOOK_WEIGHT * hook_score(opening.text)
        + _PAYOFF_WEIGHT * _payoff_score(window_text)
        + _DENSITY_WEIGHT * _density_score(window_text, window_duration)
        + _STORY_WEIGHT * _story_score(window)
        + _COMPLETENESS_WEIGHT * _completeness_score(opening.text)
    )
    score -= _MAX_FILLER_PENALTY * _filler_penalty(window_text)
    score -= _MAX_CONTINUATION_PENALTY * _continuation_penalty(opening.text)
    return round(max(score, 0.0), 4)


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

    for index, segment in enumerate(segments):
        segment.highlight_score = _score_segment(segments, index)
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
