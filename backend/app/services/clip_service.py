"""Business logic for the Clip resource.

Owned by BACKEND-AGENT (clip library module). Other module teams (B-roll,
Export) build their own sub-path endpoints under /clips/{id}/broll and
/clips/{id}/export respectively and should reuse `get_clip_owned` for
ownership checks rather than duplicating the query.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationAppError
from app.models.clip import Clip, ClipStatus
from app.models.transcript_segment import TranscriptSegment
from app.models.video_project import VideoProject, VideoProjectStatus
from app.schemas.clip import ClipUpdateRequest

_MAX_AUTO_TITLE_LEN = 40

# A single highlighted TranscriptSegment is often just one Whisper sentence
# (a few seconds), which makes a poor Short on its own. Generated clips are
# expanded around each highlight to land in this range instead.
MIN_CLIP_DURATION = 30.0
MAX_CLIP_DURATION = 50.0
TARGET_CLIP_DURATION = 40.0


def _auto_title(text: str) -> str:
    """Derive a clip title from the first ~40 chars of a transcript segment."""

    stripped = text.strip()
    if len(stripped) <= _MAX_AUTO_TITLE_LEN:
        return stripped or "Untitled clip"
    return stripped[:_MAX_AUTO_TITLE_LEN].rstrip() + "..."


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
    clusters: list[list], floor: float, ceiling: float
) -> list[tuple[float, float, TranscriptSegment]]:
    """Expand each cluster toward TARGET_CLIP_DURATION (or trim it down to
    MAX_CLIP_DURATION if it's already longer), padding only into the gap
    before the previous cluster / after the next one.

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

        if end - start > MAX_CLIP_DURATION:
            center = (start + end) / 2
            start = center - MAX_CLIP_DURATION / 2
            end = start + MAX_CLIP_DURATION
        elif end - start < TARGET_CLIP_DURATION:
            pad = TARGET_CLIP_DURATION - (end - start)
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
    each cluster is expanded (or trimmed) into a MIN_CLIP_DURATION -
    MAX_CLIP_DURATION second window -- a raw Whisper segment is often just
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

    clusters = _cluster_raw_segments(highlight_segments)
    windows = _pad_clusters(clusters, 0.0, ceiling)

    clips: list[Clip] = []
    for index, (start_time, end_time, anchor_segment) in enumerate(windows):
        clip = Clip(
            video_project_id=video_project_id,
            user_id=user_id,
            title=_auto_title(anchor_segment.text),
            start_time=start_time,
            end_time=end_time,
            order_index=index,
            status=ClipStatus.draft,
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
