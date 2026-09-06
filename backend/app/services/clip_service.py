"""Business logic for the Clip resource.

Owned by BACKEND-AGENT (clip library module). Other module teams (B-roll,
Export) build their own sub-path endpoints under /clips/{id}/broll and
/clips/{id}/export respectively and should reuse `get_clip_owned` for
ownership checks rather than duplicating the query.
"""

from __future__ import annotations

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationAppError
from app.models.clip import Clip, ClipStatus
from app.models.transcript_segment import TranscriptSegment
from app.models.video_project import (
    ClipLength,
    VideoProject,
    VideoProjectStatus,
)
from app.schemas.clip import ClipUpdateRequest
from app.services.highlight_detection import hook_score

_MAX_AUTO_TITLE_LEN = 60

# How far a clip edge may move to land between sentences instead of
# mid-word. Wide enough to reach the next pause in normal speech, narrow
# enough that the clip stays the length that was asked for.
_SNAP_TOLERANCE_SECONDS = 2.5
# Below this a snapped window is no longer a short; keep the unsnapped one.
_MIN_SNAPPED_DURATION = 8.0
# How much further than a ClipLength's own maximum a clip may stretch to
# finish an in-progress sentence, before the edge is left wherever
# _snap_to_speech put it instead. Sized to one trailing spoken sentence
# (~15 words at a typical ~3 words/sec) -- enough to catch a sentence that
# runs a beat past budget, not enough for a "fast" clip (30s max) to creep
# toward "auto" territory (40s target).
_SENTENCE_BOUNDARY_ALLOWANCE_SECONDS = 5.0
# No generated clip may be longer than this, regardless of ClipLength or
# how far away a sentence's terminal punctuation lands.
_HARD_MAX_CLIP_DURATION = 60.0
# A line shorter than this is a fragment, not a title; longer than the
# maximum and it is a paragraph.
_MIN_TITLE_WORDS = 5
_MAX_TITLE_WORDS = 22
# A title that opens mid-thought reads as a broken clip.
_CONTINUATION_START = re.compile(
    r"^\s*(and|but|so|because|which|that|then|or|of|to|in)\b", re.IGNORECASE
)

# A single highlighted TranscriptSegment is often just one Whisper sentence
# (a few seconds), which makes a poor Short on its own. Generated clips are
# expanded around each highlight to land in this range instead.
MIN_CLIP_DURATION = 30.0
MAX_CLIP_DURATION = 50.0
TARGET_CLIP_DURATION = 40.0

#: What each `ClipLength` asks for, as `(target, maximum)` seconds. The
#: submitter picks one per video: a punchy hook and a full explanation want
#: different cuts of the same footage, and that decision has to be made
#: while the clips are being cut, not trimmed back afterwards.
CLIP_LENGTH_TARGETS: dict[ClipLength, tuple[float, float]] = {
    ClipLength.auto: (TARGET_CLIP_DURATION, MAX_CLIP_DURATION),
    ClipLength.fast: (22.0, 30.0),
    ClipLength.in_depth: (52.0, 60.0),
}


def _auto_title(text: str) -> str:
    """Derive a clip title from a transcript line.

    Cut at a word boundary rather than mid-word: the title is what the
    user scans the library by, and "Here's the thing nobody te..." reads
    like a bug where "Here's the thing nobody..." reads like a title.
    """

    stripped = " ".join(text.split())
    if not stripped:
        return "Untitled clip"
    if len(stripped) <= _MAX_AUTO_TITLE_LEN:
        return stripped

    cut = stripped[:_MAX_AUTO_TITLE_LEN]
    if " " in cut:
        cut = cut[: cut.rindex(" ")]
    return cut.rstrip(" ,;:-") + "..."


def _sentences_in(
    segments: list[TranscriptSegment], start: float, end: float
) -> list[str]:
    """Rebuild whole sentences from the segments inside a window.

    Whisper breaks on pauses, not on grammar, so a segment is usually half
    a sentence ("of the biggest boy band in the world, a 24-year-old") --
    fine for captions, useless as a title. Joining until terminal
    punctuation gives back something a person actually said end to end.
    """

    sentences: list[str] = []
    current: list[str] = []
    for segment in segments:
        if segment.start_time < start or segment.end_time > end:
            continue
        text = segment.text.strip()
        if not text:
            continue
        current.append(text)
        if text.endswith((".", "!", "?")):
            sentences.append(" ".join(current))
            current = []
    if current:
        sentences.append(" ".join(current))
    return sentences


def _title_from_window(
    segments: list[TranscriptSegment], start: float, end: float, fallback: str
) -> str:
    """Title a clip from the best sentence inside it, not the first line.

    A clip opens where the story starts, which is often a setup line
    ("Oh, this is the guy?"). The sentence worth putting in the library is
    the one that would make someone stop scrolling -- so titles are picked
    by the same measure that picks hooks, over every sentence in the clip.
    """

    candidates = [
        sentence
        for sentence in _sentences_in(segments, start, end)
        if _MIN_TITLE_WORDS <= len(sentence.split()) <= _MAX_TITLE_WORDS
        and not _CONTINUATION_START.match(sentence)
    ]
    if not candidates:
        return _auto_title(fallback)

    def strength(sentence: str) -> tuple[float, int]:
        words = len(sentence.split())
        # Sayable length: a title is a line, not a paragraph.
        length_fit = 1.0 if words <= 16 else 0.5
        return hook_score(sentence) * length_fit, -abs(words - 10)

    return _auto_title(max(candidates, key=strength))


def _snap_to_speech(
    start: float,
    end: float,
    segments: list[TranscriptSegment],
    floor: float,
    ceiling: float,
) -> tuple[float, float]:
    """Move a clip's edges onto the nearest boundaries between sentences.

    A window sized purely by duration lands mid-word about as often as not,
    and a short that opens halfway through "...and that's why I" is dead on
    arrival however well it is framed. Whisper segments break on natural
    pauses, so their edges are the closest thing to sentence boundaries the
    transcript has.

    Edges only move within `_SNAP_TOLERANCE_SECONDS`, so this tidies a cut
    rather than redefining it, and never past the neighbours' territory.
    """

    starts = [
        segment.start_time
        for segment in segments
        if abs(segment.start_time - start) <= _SNAP_TOLERANCE_SECONDS
        and floor <= segment.start_time
    ]
    ends = [
        segment.end_time
        for segment in segments
        if abs(segment.end_time - end) <= _SNAP_TOLERANCE_SECONDS
        and segment.end_time <= ceiling
    ]

    snapped_start = min(starts, key=lambda value: abs(value - start), default=start)
    snapped_end = max(ends, key=lambda value: -abs(value - end), default=end)
    if snapped_end - snapped_start < _MIN_SNAPPED_DURATION:
        # Snapping collapsed the clip (a long segment straddling both
        # edges); the duration-based window was the better answer.
        return start, end
    return snapped_start, snapped_end


def _extend_to_sentence_boundary(
    start: float,
    end: float,
    segments: list[TranscriptSegment],
    floor: float,
    ceiling: float,
    allowed_duration: float,
) -> tuple[float, float]:
    """Pull a clip's edges onto sentence-terminal boundaries (segment text
    ending in `.`/`!`/`?`) when one is reachable, so a clip opens and closes
    on a complete thought instead of wherever the duration budget or the
    nearest speech pause happened to land.

    Sentence completeness outranks the exact duration target, but only up
    to `allowed_duration` (the ClipLength's own maximum plus a small,
    bounded allowance -- see _SENTENCE_BOUNDARY_ALLOWANCE_SECONDS -- capped
    at _HARD_MAX_CLIP_DURATION by the caller): `end` only ever moves
    forward to the nearest terminal boundary at or after it, and `start`
    only ever moves backward to the nearest terminal boundary at or before
    it, both re-checked against `allowed_duration` using the other edge's
    final value, so the resulting window's duration is bounded exactly.
    `floor`/`ceiling` are the neighbouring clip's own finalized/raw edge
    (never crossed), the same bounds `_pad_clusters`/`_snap_to_speech`
    already use, so the non-overlap invariant still holds. If no boundary
    is reachable within bounds, the edge is left exactly where it was
    passed in (today's snapped-or-raw result).
    """
    # ponytail: extension is forward-only for `end` / backward-only for
    # `start` -- if a sentence's terminal punctuation lands beyond
    # `allowed_duration`, the edge stays mid-sentence rather than trimming
    # back to an earlier complete sentence. Upgrade path: bounded trim-back
    # toward `target` if this turns out to matter in practice.

    ordered = sorted(segments, key=lambda s: s.start_time)

    terminal_ends = [
        seg.end_time for seg in ordered if seg.text.strip().endswith((".", "!", "?"))
    ]
    end_candidates = [
        e for e in terminal_ends if end <= e <= ceiling and e - start <= allowed_duration
    ]
    new_end = min(end_candidates, default=end)

    # A sentence starts at the transcript's very first segment, or right
    # after any segment that ended in terminal punctuation.
    terminal_starts = [
        seg.start_time
        for i, seg in enumerate(ordered)
        if i == 0 or ordered[i - 1].text.strip().endswith((".", "!", "?"))
    ]
    start_candidates = [
        s for s in terminal_starts if floor <= s <= start and new_end - s <= allowed_duration
    ]
    new_start = max(start_candidates, default=start)

    return new_start, new_end


def _clamp_start_to_boundary(
    start_time: float,
    end_time: float,
    segments: list[TranscriptSegment],
    floor: float,
    allowed_duration: float,
) -> float:
    """Pull `start_time` forward to fit `allowed_duration`, without landing
    mid-sentence (or mid-word) the way raw subtraction would.

    Only reached when `_snap_to_speech` alone has already widened a window
    past `allowed_duration` before `_extend_to_sentence_boundary` gets a
    chance to help -- an `in_depth` clip has no allowance left to absorb
    that (see `_SENTENCE_BOUNDARY_ALLOWANCE_SECONDS` /
    `_HARD_MAX_CLIP_DURATION`). Searches forward from `end_time -
    allowed_duration` for the nearest reachable boundary: a sentence-
    terminal one first (a segment whose immediately preceding segment ends
    in `.`/`!`/`?`, or the transcript's first segment), falling back to any
    segment start if none exists in range. `end_time` -- the
    sentence-terminal boundary `_extend_to_sentence_boundary` already
    landed on -- is never moved.
    """

    min_start = end_time - allowed_duration
    # A boundary within _MIN_SNAPPED_DURATION of end_time would produce a
    # zero-length or near-empty clip -- not a valid candidate however
    # "reachable" it is by position alone.
    latest_start = end_time - _MIN_SNAPPED_DURATION
    ordered = sorted(segments, key=lambda s: s.start_time)

    sentence_starts = [
        seg.start_time
        for i, seg in enumerate(ordered)
        if i == 0 or ordered[i - 1].text.strip().endswith((".", "!", "?"))
    ]
    reachable = [s for s in sentence_starts if min_start <= s <= latest_start and floor <= s]
    if reachable:
        return min(reachable)

    segment_starts = [seg.start_time for seg in ordered]
    reachable = [s for s in segment_starts if min_start <= s <= latest_start and floor <= s]
    if reachable:
        return min(reachable)

    # ponytail: no boundary at all is reachable within allowed_duration (a
    # single segment spans the whole window) -- fall back to the raw
    # duration edge so the cap is never silently exceeded, rather than
    # error or produce an empty clip. Upgrade path: bounded trim-back of
    # `end_time` instead, if this shows up outside pathological fixtures.
    return min_start


def _fallback_title_source(
    segments: list[TranscriptSegment],
    start: float,
    end: float,
    anchor: TranscriptSegment,
) -> str:
    """Text to title a clip from when no sentence in the window fits
    `_title_from_window`'s length filter.

    Prefers the cluster's own anchor highlight, but only when the anchor
    still falls inside the final (start, end) window -- a boundary clamp
    downstream of clustering (`_clamp_start_to_boundary`) can push a
    window's start past where the anchor sits, and titling a clip from a
    highlight it no longer contains is misleading, not just untidy.
    """

    if start <= anchor.start_time and anchor.end_time <= end:
        return anchor.text
    in_window = [s for s in segments if start <= s.start_time and s.end_time <= end]
    if in_window:
        return in_window[0].text
    # Anchor is outside the window and nothing else is fully inside it
    # either -- titling from the anchor here would reproduce the exact bug
    # this function exists to prevent, so degrade to "Untitled clip"
    # (via _auto_title("")) instead.
    return ""


def _cluster_raw_segments(
    segments: list[TranscriptSegment],
) -> list[list]:
    """Merge raw highlighted-segment spans that already touch/overlap into
    clusters, *before* any minimum-duration padding is applied.

    Padding is applied per-cluster afterwards (see _pad_clusters); doing the
    padding first and merging overlaps second is what caused clip generation
    to cascade -- padding highlight A into highlight B's territory, then B's
    own pad reaching C, chaining an entire video's worth of scattered
    highlights into one multi-minute "clip". Clustering raw (unpadded) spans
    first means only highlights that are *actually* adjacent in the source
    get grouped.
    """

    ordered = sorted(segments, key=lambda s: s.start_time)
    clusters: list[list] = []
    for seg in ordered:
        if clusters and seg.start_time <= clusters[-1][1]:
            clusters[-1][1] = max(clusters[-1][1], seg.end_time)
        else:
            clusters.append([seg.start_time, seg.end_time, seg])
    return clusters


def _pad_clusters(
    clusters: list[list],
    floor: float,
    ceiling: float,
    target: float = TARGET_CLIP_DURATION,
    maximum: float = MAX_CLIP_DURATION,
) -> list[tuple[float, float, TranscriptSegment]]:
    """Expand each cluster toward `target` (or trim it down to `maximum` if
    it's already longer), padding only into the gap before the previous
    cluster / after the next one.

    `target`/`maximum` come from the video's requested short length, so
    "Fast" and "In-Depth" cut differently from the same highlights.

    Processing left-to-right and bounding this cluster's "pad before" by how
    much room is left after the *previous* cluster's already-finalized end
    (rather than its raw end) guarantees windows never overlap, without
    wasting any of the available gap -- see the module's test coverage for
    the dense-highlight case this specifically fixes.
    """

    n = len(clusters)
    windows: list[tuple[float, float, TranscriptSegment]] = []
    prev_final_end = floor
    for idx, (start, end, anchor) in enumerate(clusters):
        next_raw_start = clusters[idx + 1][0] if idx < n - 1 else ceiling

        if end - start > maximum:
            center = (start + end) / 2
            start = center - maximum / 2
            end = start + maximum
        elif end - start < target:
            pad = target - (end - start)
            max_before = max(0.0, start - prev_final_end)
            max_after = max(0.0, next_raw_start - end)

            pad_before = min(pad / 2, max_before)
            pad_after = min(pad - pad_before, max_after)
            # Give any pad the first side couldn't use to the other side,
            # still bounded by that side's own available room.
            leftover = pad - pad_before - pad_after
            if leftover > 0:
                pad_before = min(pad_before + leftover, max_before)
            leftover = pad - pad_before - pad_after
            if leftover > 0:
                pad_after = min(pad_after + leftover, max_after)

            start -= pad_before
            end += pad_after

        start = max(start, prev_final_end)
        end = min(end, next_raw_start)

        windows.append((round(start, 2), round(end, 2), anchor))
        prev_final_end = end
    return windows


def create_clips_from_highlights(
    db: Session, video_project_id: int, user_id: int
) -> list[Clip]:
    """Create draft Clips from a video project's highlighted transcript segments.

    Adjacent/overlapping highlights are first grouped into clusters, then
    each cluster is expanded (or trimmed) into a window of the length the
    video was submitted with (see CLIP_LENGTH_TARGETS) -- a raw Whisper segment is often just
    one short sentence, too brief to stand alone as a Short -- without ever
    growing into a neighboring cluster's own territory, so a video with many
    scattered highlights still produces several short clips rather than one
    clip spanning most of the video.

    Raises:
        NotFoundError: the video project does not exist or is not owned by user_id.
        ValidationAppError: the video project has not finished processing
            (status != ready).
    """

    project = (
        db.query(VideoProject)
        .filter(VideoProject.id == video_project_id, VideoProject.user_id == user_id)
        .first()
    )
    if project is None:
        raise NotFoundError("Video project")

    if project.status != VideoProjectStatus.ready:
        raise ValidationAppError(
            "Video project must be status=ready before generating clips"
        )

    highlight_segments = (
        db.query(TranscriptSegment)
        .filter(
            TranscriptSegment.video_project_id == video_project_id,
            TranscriptSegment.is_highlight.is_(True),
        )
        .order_by(TranscriptSegment.start_time.asc())
        .all()
    )
    if not highlight_segments:
        return []

    ceiling = (
        db.query(func.max(TranscriptSegment.end_time))
        .filter(TranscriptSegment.video_project_id == video_project_id)
        .scalar()
        or 0.0
    )

    # Every segment, not just the highlighted ones: the edges a clip snaps
    # to are pauses in speech, and most of those sit in ordinary lines.
    all_segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.video_project_id == video_project_id)
        .order_by(TranscriptSegment.start_time.asc())
        .all()
    )

    target, maximum = CLIP_LENGTH_TARGETS[project.target_clip_length]
    allowed_duration = min(
        maximum + _SENTENCE_BOUNDARY_ALLOWANCE_SECONDS, _HARD_MAX_CLIP_DURATION
    )
    clusters = _cluster_raw_segments(highlight_segments)
    windows = _pad_clusters(clusters, 0.0, ceiling, target, maximum)

    clips: list[Clip] = []
    previous_end = 0.0
    for index, (start_time, end_time, anchor_segment) in enumerate(windows):
        next_start = windows[index + 1][0] if index + 1 < len(windows) else ceiling
        start_time, end_time = _snap_to_speech(
            start_time, end_time, all_segments, previous_end, next_start
        )
        start_time, end_time = _extend_to_sentence_boundary(
            start_time, end_time, all_segments, previous_end, next_start, allowed_duration
        )
        if end_time - start_time > allowed_duration:
            # _snap_to_speech can widen a window by up to
            # 2 * _SNAP_TOLERANCE_SECONDS on its own; for in_depth clips
            # the hard cap leaves no allowance left to absorb that. Give up
            # some of the opening rather than the sentence-terminal end
            # _extend_to_sentence_boundary just earned -- but land the new
            # opening on a boundary, not wherever raw subtraction falls.
            start_time = _clamp_start_to_boundary(
                start_time, end_time, all_segments, previous_end, allowed_duration
            )
        previous_end = end_time
        clip = Clip(
            video_project_id=video_project_id,
            user_id=user_id,
            title=_title_from_window(
                all_segments,
                start_time,
                end_time,
                _fallback_title_source(all_segments, start_time, end_time, anchor_segment),
            ),
            start_time=round(start_time, 2),
            end_time=round(end_time, 2),
            order_index=index,
            status=ClipStatus.draft,
            # Born with what the submitter asked for, so the first export
            # already looks the way they set it up.
            framing_mode=project.framing_mode,
            caption_style=project.caption_style,
        )
        db.add(clip)
        clips.append(clip)

    db.commit()
    for clip in clips:
        db.refresh(clip)

    return clips


def get_clip_owned(db: Session, clip_id: int, user_id: int) -> Clip:
    """Fetch a clip by id, scoped to the owning user.

    Raises:
        NotFoundError: no clip with that id exists, or it belongs to another user.
    """

    clip = (
        db.query(Clip).filter(Clip.id == clip_id, Clip.user_id == user_id).first()
    )
    if clip is None:
        raise NotFoundError("Clip")
    return clip


def list_clips(
    db: Session,
    user_id: int,
    video_project_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[Clip], int]:
    """List clips owned by user_id, optionally filtered by video_project_id.

    Returns (items, total).
    """

    query = db.query(Clip).filter(Clip.user_id == user_id)
    if video_project_id is not None:
        query = query.filter(Clip.video_project_id == video_project_id)

    total = query.count()
    items = (
        query.order_by(Clip.video_project_id.asc(), Clip.order_index.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def update_clip(db: Session, clip: Clip, payload: ClipUpdateRequest) -> Clip:
    """Apply a partial update to a clip's editable fields."""

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(clip, field, value)

    db.commit()
    db.refresh(clip)
    return clip


def reorder_clip(db: Session, clip: Clip, order_index: int) -> Clip:
    """Move a clip to `order_index` among siblings sharing its video_project_id."""

    clip.order_index = order_index
    db.commit()
    db.refresh(clip)
    return clip


def delete_clip(db: Session, clip: Clip) -> None:
    """Delete a clip. Cascades to its broll_assets via the ORM relationship."""

    db.delete(clip)
    db.commit()
