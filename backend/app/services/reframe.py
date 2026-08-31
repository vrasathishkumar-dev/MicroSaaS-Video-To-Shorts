"""Speaker-aware reframing: find who is talking, so the 9:16 crop stays on them.

A 16:9 broadcast centre-cropped to 9:16 keeps the middle 33% of the frame.
On a talk show that is the desk and the microphone; on a screen recording
it is an empty code editor. The person is off to one side, and in a
two-shot there are two of them, taking turns.

This module picks the crop window from the footage itself:

1. Sample low-resolution frames across the clip.
2. Split the clip into **shots** at the frames where the whole picture
   changes at once -- an edited interview cuts between angles, and each cut
   moves the subject somewhere else in the frame.
3. **Find the faces.** OpenCV's bundled Haar cascades run over the sampled
   frames (frontal, plus profile in both directions, since two people
   talking to each other are rarely looking at the camera). Detections are
   grouped into tracks -- one per person in the shot -- so a face that the
   cascade misses on some frames stays a person rather than flickering out.
4. **Pick the one who is talking.** For each track, measure how much the
   mouth region moves over each couple of seconds. The talker's mouth is
   the most active part of either face, so the crop follows the
   conversation and cuts between speakers the way an editor would --
   with a minimum hold and a margin the challenger has to beat, because
   a crop that ping-pongs on every gesture is worse than one that lags.
5. Frame them: a window tall enough for head, shoulders and some body,
   with the face near the top where it belongs in a vertical frame. A
   speaker who is small in frame -- a webcam bubble on a screen recording
   -- gets zoomed into, which is the point.

Where no face is found at all (animation, a masked or turned-away subject,
OpenCV not installed) it falls back to a **skin-tone and motion heat map**:
skin says where a person might be, motion says which part of the frame is
doing something, and the two together beat either alone. That path is
gated hard -- if the activity is spread across the frame it reports
nothing rather than guess, and the caller uses blurred-fill framing.

`compute_speaker_framing` returns None whenever it cannot make a confident
call. Callers fall back to another framing mode.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Analysis resolution. Small on purpose -- but not as small as position
# alone would need: a face in a wide two-shot is only ~5% of the frame, and
# the cascade needs enough pixels to recognise one.
_SAMPLE_WIDTH = 480
_SAMPLE_HEIGHT = 270
_SAMPLE_FPS = 4.0
_MAX_SAMPLES = 200
_SAMPLE_TIMEOUT_SECONDS = 180

# Shot detection. A cut shows up as a whole-frame change far above the
# clip's own typical frame-to-frame motion. The relative term is what
# normally decides; the absolute floor (in grey levels of mean per-pixel
# change) only stops near-still footage, where the median is ~0, from
# reporting a cut on every faint flicker.
_CUT_ABSOLUTE_THRESHOLD = 4.0
_CUT_RELATIVE_THRESHOLD = 3.0
_MIN_SHOT_SECONDS = 1.2
# Past this many shots the source is a montage with no stable subject;
# one crop for the whole clip is the honest answer.
_MAX_SHOTS = 40

# Face detection. Detection is the expensive step, so it runs on a subset
# of the sampled frames -- enough to establish who is in the shot and
# where, with the (cheap) motion signal deciding which of them is talking.
_MAX_FACE_FRAMES = 72
_FACE_MIN_SIZE_RATIO = 0.04
_FACE_SCALE_FACTOR = 1.1
_FACE_MIN_NEIGHBOURS = 5
# Two boxes overlapping this much are the same face seen by two cascades.
_FACE_MERGE_OVERLAP = 0.3
# A detection joins a track if it lands within this fraction of a face
# width of it; people sitting and talking barely move between samples.
_FACE_TRACK_DISTANCE = 0.7
_MIN_TRACK_DETECTIONS = 2

# Active-speaker switching, inside a shot that holds more than one face.
_SPEAKER_SEGMENT_SECONDS = 2.0
_MIN_SPEAKER_HOLD_SECONDS = 2.0
# How much livelier the other person's mouth has to be before the crop
# leaves the speaker it is on.
_SPEAKER_SWITCH_MARGIN = 1.35
# The mouth, as a fraction of the detected face box: the lower part,
# inset from the sides, extended past the chin to catch the jaw.
_MOUTH_TOP = 0.55
_MOUTH_BOTTOM = 1.15
_MOUTH_INSET = 0.15

# Framing around a detected face: room for head, shoulders and some body,
# with the face high in the frame the way a portrait sits.
_FACE_HEIGHT_PADDING = 4.5
_FACE_WIDTH_PADDING = 2.4
_FACE_VERTICAL_ANCHOR = 0.24

# Split screen. A shot holding more than one person in conversation is
# shown as stacked panes, one per speaker, instead of picking one of them
# and throwing the other away.
#
# Two panes, always: three in a 9:16 frame leaves each one too short to
# read, so a shot with more faces than that shows the two liveliest.
_SPLIT_PANES = 2
# A face has to move its mouth at least this much (mean per-pixel change
# per sample) to count as part of the conversation -- it keeps a poster, a
# photo on the wall, or someone asleep in shot out of the layout.
_SPLIT_MIN_ACTIVITY = 3.0
# ...and if one person is this much livelier than everyone else for the
# whole shot, it is a monologue with a listener in frame, not a
# conversation: stay on the talker.
_SPLIT_DOMINANCE = 3.0
# Splitting for less than this reads as a glitch rather than a choice.
_MIN_SPLIT_SECONDS = 2.0

# Skin tone, in YCbCr, for the no-face fallback. The chroma window is the
# classic one, widened a little on Cb/Cr so warm or cool studio lighting
# doesn't rule out a face.
_SKIN_MIN_LUMA = 60
_SKIN_MAX_LUMA = 245
_SKIN_MIN_CB, _SKIN_MAX_CB = 77, 135
_SKIN_MIN_CR, _SKIN_MAX_CR = 133, 180
# A pixel counts as skin only if it reads as skin for nearly the whole
# shot. A face holds its colour frame after frame; a warm-toned flash, a
# grade shift, or noise that wanders through the skin range does not, and
# this is what keeps a grainy source from growing face-shaped specks.
_SKIN_PERSISTENCE = 0.8
# Below this the "skin" is a handful of stray pixels; above it, the shot is
# probably a warm-graded whole frame rather than a person in it. Either way
# the motion-only map is the more trustworthy one.
_MIN_SKIN_AREA_RATIO = 0.001
_MAX_SKIN_AREA_RATIO = 0.5
# Skin still counts where nothing moves, so a speaker holding still for a
# beat doesn't lose the framing.
_SKIN_MOTION_FLOOR = 0.25

# Confidence gates for the fallback heat map. A person is a compact blob in
# one part of the frame; anything that sprawls across it -- uniform noise,
# a whole-frame transition, a busy montage -- is not a subject.
_ACTIVE_THRESHOLD = 0.5
_MAX_ACTIVE_AREA_RATIO = 0.4
_MAX_SUBJECT_WIDTH_RATIO = 0.7
_MIN_SUBJECT_FILL = 0.4
# The hottest spot has to stand out from the typical one. Where everything
# is equally active -- film grain, a noisy source, a crowd -- the peak is
# just the luckiest pixel, and following it would be superstition.
_MIN_PEAK_CONTRAST = 2.5
# Framing around a heat-map blob, which already covers more than a face.
_BLOB_HEIGHT_PADDING = 2.2
_BLOB_WIDTH_PADDING = 1.35
_BLOB_VERTICAL_ANCHOR = 0.45

# Never zoom past this much of the source height. A webcam bubble is worth
# zooming into; blowing 200 source pixels up to a 1920-tall canvas is not.
_MIN_CROP_HEIGHT_RATIO = 0.45

# Two windows closer together than this are treated as the same framing, so
# a clip doesn't get a time expression for sub-pixel-ish differences.
_SAME_FRAMING_PIXELS = 24


@dataclass(frozen=True)
class SpeakerWindow:
    """Where the crop sits from `start_time` (seconds into the clip) on."""

    start_time: float
    x: int
    y: int


@dataclass(frozen=True)
class SplitSection:
    """A stretch of the clip shown as stacked panes, one per speaker.

    `panes` are top-to-bottom, in the order the people appear left to
    right in the source, so a viewer who just saw the wide shot finds them
    where they expect.
    """

    start_time: float
    end_time: float
    panes: tuple[SpeakerWindow, ...]


@dataclass(frozen=True)
class SplitFraming:
    """The split-screen layout, where the clip has one.

    One pane size for the whole clip, for the same reason the single
    window has one: ffmpeg's `crop` cannot resize mid-stream. Panes are
    `crop_width x crop_height` in source pixels, each scaled into a
    full-width, 1/`pane_count` -tall slice of the canvas.
    """

    pane_count: int
    crop_width: int
    crop_height: int
    sections: tuple[SplitSection, ...]


@dataclass(frozen=True)
class SpeakerFraming:
    """A crop window, in source pixels, that follows the speaker.

    The window is one fixed size for the whole clip -- ffmpeg's `crop`
    cannot resize mid-stream, and a zoom that changed on every cut would
    read as a mistake anyway -- and moves when the speaker does.

    `split`, when present, covers the stretches where more than one person
    is in the conversation; those play as stacked panes over the top of
    this window, which carries the rest of the clip.
    """

    source_width: int
    source_height: int
    crop_width: int
    crop_height: int
    windows: tuple[SpeakerWindow, ...]
    split: SplitFraming | None = None


@dataclass(frozen=True)
class _Subject:
    """Someone to frame, as fractions (0-1) of the sampled frame.

    The padding and anchor travel with the subject because a face and a
    heat-map blob need different room around them: a face box is head-only
    and wants body below it, a blob is already most of a person.
    """

    centre_x: float
    centre_y: float
    width: float
    height: float
    height_padding: float
    width_padding: float
    vertical_anchor: float


class _NumpyMissing(Exception):
    """numpy is not installed, so the analysis can't run."""


def compute_speaker_framing(
    source_path: str,
    start_time: float,
    duration: float,
    target_width: int,
    target_height: int,
) -> SpeakerFraming | None:
    """Find the crop window that keeps the speaker in frame.

    Results are cached per (file, clip range, target size) so the editor's
    preview and the export don't pay for the same probe twice, and so
    re-opening a clip is instant.

    Args:
        source_path: Absolute path to the source video.
        start_time: Clip start, in seconds from the start of the source.
        duration: Clip length in seconds.
        target_width: Output canvas width (e.g. 1080).
        target_height: Output canvas height (e.g. 1920).

    Returns:
        A SpeakerFraming, or None if no confident subject was found -- in
        which case the caller should fall back to another framing mode.
    """

    try:
        stat = Path(source_path).stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        # Missing/unreadable: let the analysis fail and report it, but
        # don't let a stale cache entry answer for a file that changed.
        signature = (0, 0)

    return _cached_framing(
        source_path,
        round(start_time, 2),
        round(duration, 2),
        target_width,
        target_height,
        signature,
    )


@lru_cache(maxsize=64)
def _cached_framing(
    source_path: str,
    start_time: float,
    duration: float,
    target_width: int,
    target_height: int,
    signature: tuple[int, int],
) -> SpeakerFraming | None:
    return _compute_framing(
        source_path, start_time, duration, target_width, target_height
    )


def compute_speaker_crop(
    source_path: str,
    start_time: float,
    duration: float,
    target_width: int,
    target_height: int,
) -> tuple[int, int, str, str] | None:
    """Speaker-aware crop arguments for ffmpeg's `crop` filter.

    Returns:
        `(crop_width, crop_height, x, y)` in source pixels. `x` and `y` are
        either constants or ffmpeg time expressions that step when the crop
        moves. None if no confident crop could be found.
    """

    framing = compute_speaker_framing(
        source_path, start_time, duration, target_width, target_height
    )
    if framing is None:
        return None

    x_expression, y_expression = crop_expressions(framing.windows)
    return framing.crop_width, framing.crop_height, x_expression, y_expression


def crop_expressions(windows: Sequence[SpeakerWindow]) -> tuple[str, str]:
    """`(x, y)` for ffmpeg's `crop`, stepping wherever the window moves.

    Each is a constant when the framing never moves, and an `if(lt(t,...))`
    chain when it does.
    """

    return (
        _build_step_expression([(w.start_time, w.x) for w in windows]),
        _build_step_expression([(w.start_time, w.y) for w in windows]),
    )


def _compute_framing(
    source_path: str,
    start_time: float,
    duration: float,
    target_width: int,
    target_height: int,
) -> SpeakerFraming | None:
    """The uncached body of `compute_speaker_framing`."""

    try:
        source_width, source_height = _probe_dimensions(source_path)
    except Exception as exc:
        logger.warning("reframe: could not probe %s: %s", source_path, exc)
        return None

    target_ratio = target_width / target_height
    if source_width / source_height <= target_ratio:
        # The source is already at least as tall-and-narrow as the target;
        # there is nothing to choose between horizontally.
        return None

    try:
        samples = _analyse(source_path, start_time, duration)
    except _NumpyMissing:
        logger.warning(
            "reframe: numpy is not installed, so speaker-aware framing is "
            "unavailable; falling back to blurred-fill framing"
        )
        return None
    except Exception as exc:
        logger.warning("reframe: motion analysis failed for %s: %s", source_path, exc)
        return None

    if samples is None:
        return None

    motion, skin, luma, sample_interval = samples
    shots = _shot_windows(motion, sample_interval, duration)
    faces = _detect_faces(luma)

    moments: list[tuple[float, _Subject | None]] = []
    conversations: list[tuple[float, float, list[_Subject]]] = []
    for first, last, shot_start in shots:
        tracks = _face_tracks(faces, first, last)
        speakers = _conversation(tracks, motion, first, last) if tracks else []
        if speakers:
            # More than one person in the conversation: show them all,
            # stacked, and keep the liveliest as what plays underneath.
            shot_end = shot_start + (last - first) * sample_interval
            conversations.append((shot_start, shot_end, speakers))
            moments.append((shot_start, speakers[0]))
        elif tracks:
            moments.extend(
                _speaker_moments(
                    tracks, motion, first, last, shot_start, sample_interval
                )
            )
        else:
            moments.append(
                (shot_start, _subject_box(motion[first:last], skin[first : last + 1]))
            )

    if all(subject is None for _, subject in moments):
        logger.info(
            "reframe: no face and no single active region; falling back to "
            "blurred-fill framing"
        )
        return None

    subjects = _fill_unknown([subject for _, subject in moments])
    crop_width, crop_height = _crop_size(
        subjects, source_width, source_height, target_ratio
    )

    windows = []
    for (moment_start, _), subject in zip(moments, subjects, strict=True):
        x, y = _window_position(
            subject, crop_width, crop_height, source_width, source_height
        )
        windows.append(SpeakerWindow(start_time=moment_start, x=x, y=y))
    windows = _merge_equal_framings(windows)

    split = _split_framing(
        conversations, source_width, source_height, target_width, target_height
    )

    logger.info(
        "reframe: %s framed in a %dx%d window of %dx%d, %s%s",
        "speaker" if faces else "subject",
        crop_width,
        crop_height,
        source_width,
        source_height,
        f"held at ({windows[0].x},{windows[0].y})"
        if len(windows) == 1
        else f"moving {len(windows)} times",
        f"; {len(split.sections)} stretch(es) split between "
        f"{split.pane_count} speakers"
        if split
        else "",
    )
    return SpeakerFraming(
        source_width=source_width,
        source_height=source_height,
        crop_width=crop_width,
        crop_height=crop_height,
        windows=tuple(windows),
        split=split,
    )


def _probe_dimensions(source_path: str) -> tuple[int, int]:
    """Return the source's (width, height) in pixels."""

    import ffmpeg

    probe = ffmpeg.probe(source_path)
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return int(stream["width"]), int(stream["height"])
    raise ValueError("no video stream found")


def _analyse(source_path: str, start_time: float, duration: float):  # type: ignore[no-untyped-def]
    """Sample the clip and return `(motion, skin, luma, sample_interval)`.

    `motion` is a uint8 array of per-pixel change between consecutive
    samples, `skin` a boolean array of per-pixel skin-tone hits, `luma` the
    greyscale frames the face cascades read, and `sample_interval` the
    wall-clock seconds between samples. Returns None when too few frames
    came back to compare.
    """

    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised via the caller
        raise _NumpyMissing from exc

    fps = _SAMPLE_FPS
    if duration * fps > _MAX_SAMPLES:
        fps = _MAX_SAMPLES / max(duration, 0.1)

    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{start_time:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            source_path,
            "-vf",
            f"fps={fps:.4f},scale={_SAMPLE_WIDTH}:{_SAMPLE_HEIGHT}",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "-",
        ],
        capture_output=True,
        check=True,
        timeout=_SAMPLE_TIMEOUT_SECONDS,
    )

    pixels_per_frame = _SAMPLE_WIDTH * _SAMPLE_HEIGHT * 3
    frame_count = len(result.stdout) // pixels_per_frame
    if frame_count < 2:
        return None

    frames = np.frombuffer(
        result.stdout[: frame_count * pixels_per_frame], dtype=np.uint8
    ).reshape(frame_count, _SAMPLE_HEIGHT, _SAMPLE_WIDTH, 3)

    motion = np.empty((frame_count - 1, _SAMPLE_HEIGHT, _SAMPLE_WIDTH), dtype=np.uint8)
    skin = np.empty((frame_count, _SAMPLE_HEIGHT, _SAMPLE_WIDTH), dtype=bool)
    luma_frames = np.empty(
        (frame_count, _SAMPLE_HEIGHT, _SAMPLE_WIDTH), dtype=np.uint8
    )

    # Frame at a time: the integer YCbCr conversion needs a wider dtype
    # than uint8, and doing it on the whole stack at once would cost an
    # order of magnitude more memory for no speed that matters here.
    previous_luma = None
    for index in range(frame_count):
        frame = frames[index].astype(np.int32)
        red, green, blue = frame[..., 0], frame[..., 1], frame[..., 2]
        luma = (77 * red + 150 * green + 29 * blue) >> 8
        chroma_blue = 128 + ((-43 * red - 85 * green + 128 * blue) >> 8)
        chroma_red = 128 + ((128 * red - 107 * green - 21 * blue) >> 8)

        luma_frames[index] = luma
        skin[index] = (
            (luma >= _SKIN_MIN_LUMA)
            & (luma <= _SKIN_MAX_LUMA)
            & (chroma_blue >= _SKIN_MIN_CB)
            & (chroma_blue <= _SKIN_MAX_CB)
            & (chroma_red >= _SKIN_MIN_CR)
            & (chroma_red <= _SKIN_MAX_CR)
        )
        if previous_luma is not None:
            motion[index - 1] = np.abs(luma - previous_luma).astype(np.uint8)
        previous_luma = luma

    return motion, skin, luma_frames, 1.0 / fps


def _shot_windows(motion, sample_interval: float, duration: float):  # type: ignore[no-untyped-def]
    """Split the sampled timeline into shots at whole-frame changes.

    Returns a list of `(first_row, last_row, start_seconds)` -- row indices
    into `motion`, and the shot's start time relative to the clip.
    """

    import numpy as np

    row_count = motion.shape[0]
    # Mean change across the whole frame: a cut spikes it, a talking head
    # barely moves it.
    frame_change = motion.mean(axis=(1, 2))
    threshold = max(
        _CUT_ABSOLUTE_THRESHOLD,
        _CUT_RELATIVE_THRESHOLD * float(np.median(frame_change)),
    )

    boundaries = [0]
    minimum_rows = max(1, int(_MIN_SHOT_SECONDS / sample_interval))
    for row in range(1, row_count):
        if frame_change[row] > threshold and row - boundaries[-1] >= minimum_rows:
            boundaries.append(row)

    if len(boundaries) > _MAX_SHOTS:
        logger.info(
            "reframe: %d shots is more than a stable subject implies; using one "
            "crop for the whole clip",
            len(boundaries),
        )
        boundaries = [0]

    shots = []
    for index, first in enumerate(boundaries):
        last = boundaries[index + 1] if index + 1 < len(boundaries) else row_count
        start_seconds = 0.0 if index == 0 else min(first * sample_interval, duration)
        shots.append((first, last, start_seconds))
    return shots


# ---------------------------------------------------------------------------
# Faces
# ---------------------------------------------------------------------------


def _detect_faces(luma) -> dict[int, list[tuple[int, int, int, int]]]:  # type: ignore[no-untyped-def]
    """Face boxes per sampled frame, as `{frame_index: [(x, y, w, h), ...]}`.

    Runs the frontal cascade plus the profile cascade in both directions --
    two people talking to each other are side-on to the camera most of the
    time, and the profile cascade only recognises one of the two
    directions, so the frame is mirrored and searched again.

    Returns an empty dict when OpenCV isn't installed, which is not an
    error: the caller falls back to the skin-and-motion heat map.
    """

    try:
        import cv2
    except ImportError:
        logger.info(
            "reframe: OpenCV is not installed, so face detection is "
            "unavailable; using the skin-and-motion fallback"
        )
        return {}

    try:
        import numpy as np

        cascade_dir = cv2.data.haarcascades
        frontal = cv2.CascadeClassifier(cascade_dir + "haarcascade_frontalface_alt2.xml")
        profile = cv2.CascadeClassifier(cascade_dir + "haarcascade_profileface.xml")
        if frontal.empty() or profile.empty():
            logger.info(
                "reframe: this OpenCV build ships no face cascades; using the "
                "skin-and-motion fallback"
            )
            return {}
    except Exception as exc:
        logger.warning("reframe: could not load face cascades: %s", exc)
        return {}

    frame_count = luma.shape[0]
    stride = max(1, -(-frame_count // _MAX_FACE_FRAMES))
    minimum = int(_SAMPLE_WIDTH * _FACE_MIN_SIZE_RATIO)
    detections: dict[int, list[tuple[int, int, int, int]]] = {}

    for index in range(0, frame_count, stride):
        grey = cv2.equalizeHist(np.ascontiguousarray(luma[index]))
        boxes: list[tuple[int, int, int, int]] = []
        for detector, mirrored in ((frontal, False), (profile, False), (profile, True)):
            image = cv2.flip(grey, 1) if mirrored else grey
            for x, y, width, height in detector.detectMultiScale(
                image,
                scaleFactor=_FACE_SCALE_FACTOR,
                minNeighbors=_FACE_MIN_NEIGHBOURS,
                minSize=(minimum, minimum),
            ):
                if mirrored:
                    x = _SAMPLE_WIDTH - int(x) - int(width)
                boxes.append((int(x), int(y), int(width), int(height)))

        merged = _merge_overlapping(boxes)
        if merged:
            detections[index] = merged

    logger.debug(
        "reframe: faces found on %d of %d sampled frames",
        len(detections),
        len(range(0, frame_count, stride)),
    )
    return detections


def _merge_overlapping(
    boxes: list[tuple[int, int, int, int]],
) -> list[tuple[int, int, int, int]]:
    """Collapse boxes that are the same face seen by two cascades."""

    merged: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda b: b[2] * b[3], reverse=True):
        if any(_overlap(box, kept) > _FACE_MERGE_OVERLAP for kept in merged):
            continue
        merged.append(box)
    return merged


def _overlap(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    """Intersection over the smaller box's area."""

    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    wide = min(ax + aw, bx + bw) - max(ax, bx)
    tall = min(ay + ah, by + bh) - max(ay, by)
    if wide <= 0 or tall <= 0:
        return 0.0
    return (wide * tall) / min(aw * ah, bw * bh)


def _face_tracks(
    detections: dict[int, list[tuple[int, int, int, int]]],
    first_row: int,
    last_row: int,
) -> list[list[tuple[int, tuple[int, int, int, int]]]]:
    """Group this shot's detections into one track per person.

    A detection joins the nearest track whose typical face is close by
    relative to its own size; people sitting and talking barely move
    between samples, so this is enough to keep two speakers apart without
    a real tracker. Matching against the track's *median* box rather than
    its latest detection matters: the frontal and profile cascades frame
    the same head slightly differently, and chasing the last hit lets one
    person drift into two tracks.

    Tracks are then merged where they turn out to sit on top of each other,
    dropped if they were seen only once, and returned left to right so a
    split screen puts people where the viewer last saw them.
    """

    tracks: list[list[tuple[int, tuple[int, int, int, int]]]] = []
    for index in sorted(detections):
        if not first_row <= index <= last_row:
            continue
        for box in detections[index]:
            best: list[tuple[int, tuple[int, int, int, int]]] | None = None
            best_distance = None
            for track in tracks:
                typical = _median_box(track)
                distance = _centre_distance(box, typical)
                allowed = _FACE_TRACK_DISTANCE * max(box[2], typical[2])
                if distance <= allowed and (
                    best_distance is None or distance < best_distance
                ):
                    best, best_distance = track, distance
            if best is None:
                tracks.append([(index, box)])
            else:
                best.append((index, box))

    tracks = _merge_overlapping_tracks(tracks)
    kept = [track for track in tracks if len(track) >= _MIN_TRACK_DETECTIONS]
    return sorted(kept, key=lambda track: _median_box(track)[0])


def _merge_overlapping_tracks(
    tracks: list[list[tuple[int, tuple[int, int, int, int]]]],
) -> list[list[tuple[int, tuple[int, int, int, int]]]]:
    """Fold together tracks whose faces occupy the same place in frame."""

    merged: list[list[tuple[int, tuple[int, int, int, int]]]] = []
    for track in sorted(tracks, key=len, reverse=True):
        box = _median_box(track)
        for kept in merged:
            if _overlap(_as_box(box), _as_box(_median_box(kept))) > _FACE_MERGE_OVERLAP:
                kept.extend(track)
                break
        else:
            merged.append(list(track))
    return merged


def _as_box(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Round a median box back to whole pixels."""

    x, y, width, height = box
    return int(round(x)), int(round(y)), int(round(width)), int(round(height))


def _centre_distance(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    """Distance between two boxes' centres, in pixels."""

    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    dx = (ax + aw / 2) - (bx + bw / 2)
    dy = (ay + ah / 2) - (by + bh / 2)
    return (dx * dx + dy * dy) ** 0.5


def _speaker_moments(  # type: ignore[no-untyped-def]
    tracks,
    motion,
    first_row: int,
    last_row: int,
    shot_start: float,
    sample_interval: float,
) -> list[tuple[float, _Subject]]:
    """Who to frame, and from when, across one shot.

    The shot is walked in short segments; in each, the face whose mouth
    region moved most is the one talking. The crop only leaves the speaker
    it is on when someone else beats them by a clear margin and the current
    framing has had its minimum hold, so a nod or a gesture can't start a
    tennis match.
    """

    segment_rows = max(1, int(round(_SPEAKER_SEGMENT_SECONDS / sample_interval)))
    hold_rows = max(1, int(round(_MIN_SPEAKER_HOLD_SECONDS / sample_interval)))

    moments: list[tuple[float, _Subject]] = []
    current: int | None = None
    held_since = first_row

    for row in range(first_row, last_row, segment_rows):
        segment = motion[row : min(row + segment_rows, last_row)]
        if segment.shape[0] == 0:
            break

        scores = [_mouth_activity(segment, _median_box(track)) for track in tracks]
        leader = max(range(len(tracks)), key=lambda index: scores[index])

        if current is None:
            current = leader
        elif leader != current and row - held_since >= hold_rows:
            challenger, incumbent = scores[leader], scores[current]
            if challenger > incumbent * _SPEAKER_SWITCH_MARGIN:
                current = leader
                held_since = row

        subject = _face_subject(_median_box(tracks[current]))
        start = shot_start + (row - first_row) * sample_interval
        if not moments or moments[-1][1] != subject:
            moments.append((start if moments else shot_start, subject))

    return moments


def _median_box(
    track: list[tuple[int, tuple[int, int, int, int]]],
) -> tuple[float, float, float, float]:
    """The track's typical face box, immune to one bad detection."""

    import numpy as np

    boxes = np.array([box for _, box in track], dtype=float)
    return tuple(np.median(boxes, axis=0))  # type: ignore[return-value]


def _mouth_activity(segment, box: tuple[float, float, float, float]) -> float:  # type: ignore[no-untyped-def]
    """Mean motion in a face's mouth region over `segment`.

    Per-pixel, so a face close to camera doesn't out-score a smaller one
    just by covering more of the frame.
    """

    x, y, width, height = box
    left = int(round(x + _MOUTH_INSET * width))
    right = int(round(x + (1 - _MOUTH_INSET) * width))
    top = int(round(y + _MOUTH_TOP * height))
    bottom = int(round(y + _MOUTH_BOTTOM * height))

    left = max(0, min(left, _SAMPLE_WIDTH - 1))
    right = max(left + 1, min(right, _SAMPLE_WIDTH))
    top = max(0, min(top, _SAMPLE_HEIGHT - 1))
    bottom = max(top + 1, min(bottom, _SAMPLE_HEIGHT))

    return float(segment[:, top:bottom, left:right].mean())


def _conversation(  # type: ignore[no-untyped-def]
    tracks,
    motion,
    first_row: int,
    last_row: int,
) -> list[_Subject]:
    """The people to put on screen together, or [] for a single speaker.

    A shot earns a split screen when more than one face in it is actually
    doing something with its mouth over the shot. Two caveats keep the
    layout honest:

    - A face that never moves is a photo, a poster, or somebody asleep --
      it is in the shot, not in the conversation.
    - One person far livelier than everyone else for the whole shot is
      giving a monologue while someone listens; splitting the screen would
      hand half of it to a nodding head, so the crop stays on the talker.

    Returned liveliest-first so the caller can pick a lead, then reordered
    left to right by the caller that lays out the panes.
    """

    if len(tracks) < 2:
        return []

    segment = motion[first_row:last_row]
    if segment.shape[0] == 0:
        return []

    scored = sorted(
        ((_mouth_activity(segment, _median_box(track)), track) for track in tracks),
        key=lambda pair: pair[0],
        reverse=True,
    )
    talking = [pair for pair in scored if pair[0] >= _SPLIT_MIN_ACTIVITY]
    if len(talking) < 2:
        return []
    if talking[0][0] > talking[1][0] * _SPLIT_DOMINANCE:
        return []

    return [_face_subject(_median_box(track)) for _, track in talking[:_SPLIT_PANES]]


def _split_framing(
    conversations: list[tuple[float, float, list[_Subject]]],
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> SplitFraming | None:
    """Lay the conversation stretches out as stacked panes.

    Each pane is a full-width, 1/n-tall slice of the canvas, so a pane's
    crop takes the canvas aspect divided by n -- wider and shorter than the
    single-speaker window, which is why the split carries its own size.
    """

    sections = [
        (start, end, speakers)
        for start, end, speakers in conversations
        if end - start >= _MIN_SPLIT_SECONDS
    ]
    if not sections:
        return None

    pane_count = _SPLIT_PANES
    pane_ratio = target_width / (target_height / pane_count)
    crop_width, crop_height = _crop_size(
        [subject for _, _, speakers in sections for subject in speakers],
        source_width,
        source_height,
        pane_ratio,
    )

    laid_out = []
    for start, end, speakers in sections:
        # Top to bottom in the order they sit left to right on screen.
        ordered = sorted(speakers, key=lambda subject: subject.centre_x)
        panes = []
        for subject in ordered[:pane_count]:
            x, y = _window_position(
                subject, crop_width, crop_height, source_width, source_height
            )
            panes.append(SpeakerWindow(start_time=start, x=x, y=y))
        while len(panes) < pane_count:
            # Should not happen -- a conversation has at least two people
            # -- but a short pane list would break the fixed layout.
            panes.append(panes[-1])
        laid_out.append(
            SplitSection(start_time=start, end_time=end, panes=tuple(panes))
        )

    return SplitFraming(
        pane_count=pane_count,
        crop_width=crop_width,
        crop_height=crop_height,
        sections=tuple(laid_out),
    )


def _face_subject(box: tuple[float, float, float, float]) -> _Subject:
    """Turn a face box into someone to frame, with room for their body."""

    x, y, width, height = box
    return _Subject(
        centre_x=(x + width / 2) / _SAMPLE_WIDTH,
        centre_y=(y + height / 2) / _SAMPLE_HEIGHT,
        width=width / _SAMPLE_WIDTH,
        height=height / _SAMPLE_HEIGHT,
        height_padding=_FACE_HEIGHT_PADDING,
        width_padding=_FACE_WIDTH_PADDING,
        vertical_anchor=_FACE_VERTICAL_ANCHOR,
    )


# ---------------------------------------------------------------------------
# Fallback: skin tone and motion
# ---------------------------------------------------------------------------


def _subject_box(motion_rows, skin_rows) -> _Subject | None:  # type: ignore[no-untyped-def]
    """Locate a subject in a shot where no face was found.

    Returns their centre and bounding box as fractions of the frame, or
    None when nothing in the shot looks like one person.
    """

    import numpy as np

    if motion_rows.shape[0] == 0 or skin_rows.shape[0] == 0:
        return None

    # Median over time: one gesture or one flash frame can't drag the
    # answer the way a mean would.
    strength = np.median(motion_rows.astype(np.float32), axis=0)
    peak_motion = float(strength.max())
    motion_map = strength / peak_motion if peak_motion > 0 else strength

    persistence = skin_rows.mean(axis=0)
    skin_area = float((persistence >= _SKIN_PERSISTENCE).mean())
    if _MIN_SKIN_AREA_RATIO <= skin_area <= _MAX_SKIN_AREA_RATIO:
        # Skin says where a person is; motion says which of them is the one
        # doing something. A face that is both wins outright.
        heat = np.where(persistence >= _SKIN_PERSISTENCE, persistence, 0.0) * (
            _SKIN_MOTION_FLOOR + motion_map
        )
    else:
        heat = motion_map

    # Smooth over ~7% of the width so a single noisy pixel can't win.
    heat = _box_blur(heat, max(3, _SAMPLE_WIDTH // 14) | 1)
    peak = float(heat.max())
    if peak <= 0:
        return None
    if peak < _MIN_PEAK_CONTRAST * float(np.median(heat)):
        return None

    heat = heat - heat.min()
    peak = float(heat.max())
    if peak <= 0:
        return None
    heat = heat / peak

    active = heat >= _ACTIVE_THRESHOLD
    if not active.any():
        return None
    if float(active.mean()) > _MAX_ACTIVE_AREA_RATIO:
        return None

    # Only the blob containing the hottest pixel: two people in shot means
    # framing the one actually doing the talking, not the midpoint between
    # them, and scattered activity stays scattered instead of merging into
    # one frame-wide "subject".
    region = _peak_region(active, heat)

    height, width = heat.shape
    rows, columns = np.nonzero(region)
    box_width = int(columns.max() - columns.min() + 1)
    box_height = int(rows.max() - rows.min() + 1)
    if box_width / width > _MAX_SUBJECT_WIDTH_RATIO:
        # Nothing to choose between horizontally -- it spans the frame.
        return None
    if int(region.sum()) / (box_width * box_height) < _MIN_SUBJECT_FILL:
        # A sprawl of disconnected specks, not a person.
        return None

    weights = np.where(region, heat, 0.0)
    total = float(weights.sum())
    centre_x = float((weights.sum(axis=0) * np.arange(width)).sum()) / total
    centre_y = float((weights.sum(axis=1) * np.arange(height)).sum()) / total

    return _Subject(
        centre_x=centre_x / width,
        centre_y=centre_y / height,
        width=box_width / width,
        height=box_height / height,
        height_padding=_BLOB_HEIGHT_PADDING,
        width_padding=_BLOB_WIDTH_PADDING,
        vertical_anchor=_BLOB_VERTICAL_ANCHOR,
    )


def _peak_region(active, heat):  # type: ignore[no-untyped-def]
    """The connected run of active pixels containing the hottest one.

    Grown by repeated 4-neighbour dilation clipped to `active`, which on a
    frame this small settles in a few milliseconds and saves depending on
    scipy for one label pass.
    """

    import numpy as np

    seed = np.unravel_index(int(np.argmax(np.where(active, heat, -1.0))), heat.shape)
    region = np.zeros_like(active)
    region[seed] = True

    for _ in range(sum(active.shape)):
        grown = region.copy()
        grown[1:, :] |= region[:-1, :]
        grown[:-1, :] |= region[1:, :]
        grown[:, 1:] |= region[:, :-1]
        grown[:, :-1] |= region[:, 1:]
        grown &= active
        if int(grown.sum()) == int(region.sum()):
            break
        region = grown
    return region


def _box_blur(image, size: int):  # type: ignore[no-untyped-def]
    """Separable box blur, applied along each axis in turn."""

    import numpy as np

    kernel = np.ones(size) / size
    blurred = np.apply_along_axis(
        lambda row: np.convolve(row, kernel, mode="same"), 1, image
    )
    return np.apply_along_axis(
        lambda column: np.convolve(column, kernel, mode="same"), 0, blurred
    )


# ---------------------------------------------------------------------------
# Turning subjects into a crop window
# ---------------------------------------------------------------------------


def _fill_unknown(subjects: list[_Subject | None]) -> list[_Subject]:
    """Give moments with no confident subject their neighbour's framing.

    Holding the previous framing through an establishing shot or a cutaway
    is far less jarring than snapping back to centre for a second.
    """

    known = [subject for subject in subjects if subject is not None]
    last = known[0]

    filled: list[_Subject] = []
    for subject in subjects:
        if subject is None:
            filled.append(last)
        else:
            filled.append(subject)
            last = subject
    return filled


def _crop_size(
    subjects: list[_Subject],
    source_width: int,
    source_height: int,
    target_ratio: float,
) -> tuple[int, int]:
    """Pick the one crop size that holds every subject in the clip.

    The largest subject sets the size, so nobody ends up half outside the
    frame; the floor stops a tiny subject -- a webcam bubble -- from being
    blown up past what the source can carry.
    """

    needed = max(
        max(
            subject.height * source_height * subject.height_padding,
            subject.width * source_width * subject.width_padding / target_ratio,
        )
        for subject in subjects
    )
    crop_height = min(max(needed, _MIN_CROP_HEIGHT_RATIO * source_height), source_height)
    crop_width = crop_height * target_ratio
    if crop_width > source_width:
        crop_width = float(source_width)
        crop_height = crop_width / target_ratio

    # Even dimensions keep yuv420p happy; width follows height so the
    # window keeps the target's aspect and `scale` doesn't distort.
    crop_height_px = min(int(crop_height) & ~1, source_height & ~1)
    crop_width_px = min(
        int(round(crop_height_px * target_ratio)) & ~1, source_width & ~1
    )
    return crop_width_px, crop_height_px


def _window_position(
    subject: _Subject,
    crop_width: int,
    crop_height: int,
    source_width: int,
    source_height: int,
) -> tuple[int, int]:
    """Top-left corner of the crop window for one subject."""

    x = subject.centre_x * source_width - crop_width / 2
    y = subject.centre_y * source_height - crop_height * subject.vertical_anchor
    return (
        _clamp_even(x, source_width - crop_width),
        _clamp_even(y, source_height - crop_height),
    )


def _clamp_even(value: float, maximum: int) -> int:
    """Round to an even pixel inside `[0, maximum]`."""

    return max(0, min(int(round(value)), maximum)) & ~1


def _merge_equal_framings(windows: list[SpeakerWindow]) -> list[SpeakerWindow]:
    """Drop moves that don't actually change the framing."""

    merged: list[SpeakerWindow] = []
    for window in windows:
        if (
            merged
            and abs(window.x - merged[-1].x) <= _SAME_FRAMING_PIXELS
            and abs(window.y - merged[-1].y) <= _SAME_FRAMING_PIXELS
        ):
            continue
        merged.append(window)
    return merged


def _build_step_expression(positions: list[tuple[float, int]]) -> str:
    """Build an ffmpeg `crop` expression that steps when the crop moves.

    Produces `if(lt(t,T1),V0,if(lt(t,T2),V1,V2))`. ffmpeg-python escapes the
    commas for the filtergraph, so this can be passed straight through as a
    filter argument.
    """

    expression = str(positions[-1][1])
    for index in range(len(positions) - 2, -1, -1):
        boundary = positions[index + 1][0]
        expression = f"if(lt(t,{boundary:.2f}),{positions[index][1]},{expression})"
    return expression


def reframe_enabled() -> bool:
    """Whether the configured framing mode wants speaker-aware cropping."""

    return settings.RENDER_FRAMING.lower() == "auto"
