"""Tests for speaker-aware reframing (app.services.reframe).

The expression helpers are pure logic; the detection tests drive the real
ffmpeg sampling path against synthesised footage whose subject is in a
known place, so a regression in the analysis shows up as a crop window that
doesn't contain the person.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from app.services.reframe import (
    _SAMPLE_HEIGHT,
    _SAMPLE_WIDTH,
    SpeakerFraming,
    SpeakerWindow,
    _build_step_expression,
    _conversation,
    _face_subject,
    _face_tracks,
    _fill_unknown,
    _merge_equal_framings,
    _merge_overlapping,
    _speaker_moments,
    _split_framing,
    _Subject,
    compute_speaker_crop,
    compute_speaker_framing,
)


def _make_source_with_speaker_at(
    path: Path,
    x: int,
    width: int = 1280,
    height: int = 720,
    duration: float = 3.0,
    size: int = 240,
) -> None:
    """Synthesize a still frame with a skin-toned, moving figure at `x`.

    Stands in for a speaker: warm-toned (so the skin test finds it) and
    never quite still (so the motion test agrees), against a flat
    background that is neither.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x2A3138:s={width}x{height}:r=25:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0xC98A63:s={size}x{size}:r=25:d={duration}",
            "-filter_complex",
            "[1:v]noise=alls=8:allf=t[speaker];"
            f"[0:v][speaker]overlay=x={x}:y={(height - size) // 2}+12*sin(t*3)",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _make_greyscale_source_with_motion_at(
    path: Path, x: int, width: int = 1280, height: int = 720, duration: float = 3.0
) -> None:
    """Synthesize greyscale footage whose only moving patch is at `x`.

    Grey has no skin tone anywhere in it, so this drives the motion-only
    fallback -- the path that has to still work for animation, heavy
    grading, or a subject the chroma test can't see.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=gray:s={width}x{height}:r=25:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=s=240x240:r=25:d={duration}",
            "-filter_complex",
            f"[0:v][1:v]overlay=x={x}:y={(height - 240) // 2},format=gray",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _make_screen_recording_with_webcam(
    path: Path,
    face_x: int,
    face_y: int,
    face_size: int = 260,
    width: int = 1920,
    height: int = 1080,
    duration: float = 6.0,
) -> None:
    """Synthesize a screen recording with a small webcam bubble.

    A dark editor pane fills most of the frame and churns constantly (the
    busiest thing on screen by a wide margin); the speaker is a small,
    skin-toned, gently moving patch off in a corner. Motion alone would
    frame the editor -- this is the case that has to pick the person.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x101418:s={width}x{height}:r=25:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=s=900x200:r=25:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0xC98A63:s={face_size}x{face_size}:r=25:d={duration}",
            "-filter_complex",
            "[1:v]eq=saturation=0.15:brightness=-0.35[editor];"
            "[0:v][editor]overlay=x=120:y=300[desktop];"
            "[2:v]noise=alls=8:allf=t[face];"
            f"[desktop][face]overlay=x={face_x}:y={face_y}+20*sin(t*3)",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def _concatenate(parts: list[Path], output: Path) -> None:
    """Join clips end to end, producing a hard cut between each."""

    list_file = output.with_suffix(".txt")
    list_file.write_text("".join(f"file '{part}'\n" for part in parts), encoding="utf-8")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(output),
        ],
        check=True,
        capture_output=True,
    )


def _make_two_speaker_interview(tmp_path: Path) -> Path:
    """Two speakers, one per shot, joined by a hard cut."""

    left = tmp_path / "part_left.mp4"
    right = tmp_path / "part_right.mp4"
    _make_source_with_speaker_at(left, x=100, duration=3.0)
    _make_source_with_speaker_at(right, x=940, duration=3.0)
    source = tmp_path / "interview.mp4"
    _concatenate([left, right], source)
    return source


def _contains(
    framing: SpeakerFraming, window: SpeakerWindow, box: tuple[int, int, int, int]
) -> bool:
    """Whether `window` fully contains `box` = (x0, y0, x1, y1)."""

    x0, y0, x1, y1 = box
    return (
        window.x <= x0
        and window.y <= y0
        and window.x + framing.crop_width >= x1
        and window.y + framing.crop_height >= y1
    )


def _subject(centre_x: float) -> _Subject:
    return _Subject(
        centre_x=centre_x,
        centre_y=0.5,
        width=0.2,
        height=0.3,
        height_padding=2.2,
        width_padding=1.35,
        vertical_anchor=0.45,
    )


class TestExpressionHelpers:
    def test_single_shot_needs_no_conditional(self) -> None:
        assert _build_step_expression([(0.0, 512, True)]) == "512"

    def test_the_crop_snaps_at_a_cut(self) -> None:
        """The picture changes at that instant anyway; panning across a cut
        would slide over footage that has already moved on."""

        expression = _build_step_expression(
            [(0.0, 100, True), (2.0, 800, True), (5.5, 300, True)]
        )

        assert expression == "if(lt(t,2.00),100,if(lt(t,5.50),800,300))"

    def test_the_crop_eases_when_it_moves_inside_a_shot(self) -> None:
        expression = _build_step_expression([(0.0, 100, True), (2.0, 800, False)])

        # Holds, travels for half a second, then rests on the new position.
        assert expression.startswith("if(lt(t,2.00),100,if(lt(t,2.50),")
        assert expression.endswith(",800))")
        assert "clip((t-2.00)/0.50,0,1)" in expression

    def test_a_move_that_goes_nowhere_needs_no_ramp(self) -> None:
        expression = _build_step_expression([(0.0, 400, True), (2.0, 400, False)])

        assert expression == "if(lt(t,2.00),400,400)"

    def test_near_identical_framings_are_merged(self) -> None:
        # 3px apart is the same shot as far as the viewer is concerned;
        # 400px apart is a different speaker.
        merged = _merge_equal_framings(
            [
                SpeakerWindow(0.0, 800, 200),
                SpeakerWindow(2.0, 803, 198),
                SpeakerWindow(4.0, 400, 200),
            ]
        )

        assert merged == [SpeakerWindow(0.0, 800, 200), SpeakerWindow(4.0, 400, 200)]

    def test_a_vertical_move_alone_is_still_a_reframe(self) -> None:
        """The speaker standing up moves the crop even though x barely
        changes -- framing is 2-D now, not a column."""

        merged = _merge_equal_framings(
            [SpeakerWindow(0.0, 800, 600), SpeakerWindow(2.0, 802, 100)]
        )

        assert len(merged) == 2

    def test_shots_without_a_confident_subject_hold_the_previous_framing(self) -> None:
        left, right = _subject(0.8), _subject(0.2)

        assert _fill_unknown([left, None, None, right]) == [left, left, left, right]

    def test_a_leading_unknown_shot_borrows_the_first_known_one(self) -> None:
        only = _subject(0.3)

        assert _fill_unknown([None, only]) == [only, only]


class TestFaceGrouping:
    """Turning raw cascade hits into one track per person."""

    def test_the_same_face_seen_by_two_cascades_counts_once(self) -> None:
        frontal = (100, 50, 60, 60)
        profile = (104, 54, 58, 58)
        far_away = (300, 50, 60, 60)

        merged = _merge_overlapping([frontal, profile, far_away])

        assert sorted(merged) == sorted([frontal, far_away])

    def test_two_people_become_two_tracks(self) -> None:
        detections = {
            0: [(100, 50, 60, 60), (300, 50, 60, 60)],
            4: [(104, 52, 60, 60), (298, 48, 60, 60)],
            8: [(102, 51, 60, 60), (301, 52, 60, 60)],
        }

        tracks = _face_tracks(detections, 0, 8)

        assert len(tracks) == 2
        assert sorted(len(track) for track in tracks) == [3, 3]

    def test_a_one_frame_false_positive_is_dropped(self) -> None:
        detections = {
            0: [(100, 50, 60, 60)],
            4: [(102, 51, 60, 60), (700, 200, 40, 40)],
            8: [(101, 52, 60, 60)],
        }

        tracks = _face_tracks(detections, 0, 8)

        assert len(tracks) == 1

    def test_detections_outside_the_shot_are_ignored(self) -> None:
        detections = {
            0: [(100, 50, 60, 60)],
            4: [(102, 51, 60, 60)],
            40: [(700, 200, 60, 60)],
            44: [(702, 201, 60, 60)],
        }

        tracks = _face_tracks(detections, 0, 8)

        assert len(tracks) == 1


class TestActiveSpeaker:
    """Which of the faces in shot the crop should be on."""

    @staticmethod
    def _two_speakers(
        talking_first: slice, talking_second: slice, rows: int = 40
    ) -> tuple[list[list[tuple[int, tuple[int, int, int, int]]]], object]:
        """A motion stack where each speaker's mouth moves in its own rows."""

        import numpy as np

        left = (60, 60, 60, 60)
        right = (340, 60, 60, 60)
        motion = np.zeros((rows, _SAMPLE_HEIGHT, _SAMPLE_WIDTH), dtype=np.uint8)
        # Mouth region of each face box: the lower part, inset from the sides.
        motion[talking_first, 95:130, 70:110] = 200
        motion[talking_second, 95:130, 350:390] = 200

        tracks = [
            [(row, left) for row in range(0, rows, 4)],
            [(row, right) for row in range(0, rows, 4)],
        ]
        return tracks, motion

    def test_the_crop_cuts_to_whoever_is_talking(self) -> None:
        tracks, motion = self._two_speakers(slice(0, 20), slice(20, 40))

        moments = _speaker_moments(tracks, motion, 0, 40, 0.0, 0.25)

        assert len(moments) >= 2, "never left the first speaker"
        assert moments[0][1].centre_x < 0.5, "did not start on the left speaker"
        assert moments[-1][1].centre_x > 0.5, "did not cut to the right speaker"
        # The switch lands where the conversation actually turns over.
        assert 4.0 <= moments[-1][0] <= 6.5, moments[-1][0]

    def test_a_brief_interjection_does_not_start_a_tennis_match(self) -> None:
        """Half a second of the other person nodding is not a new speaker."""

        import numpy as np

        tracks, motion = self._two_speakers(slice(0, 40), slice(0, 0))
        motion[np.s_[18:20], 95:130, 350:390] = 255

        moments = _speaker_moments(tracks, motion, 0, 40, 0.0, 0.25)

        assert len(moments) == 1
        assert moments[0][1].centre_x < 0.5

    def test_the_framing_leaves_room_for_a_body_under_the_face(self) -> None:
        tracks, motion = self._two_speakers(slice(0, 40), slice(0, 0))

        subject = _speaker_moments(tracks, motion, 0, 40, 0.0, 0.25)[0][1]

        # A face box alone would frame a floating head; the crop is sized
        # several face-heights tall with the face high in it.
        assert subject.height_padding >= 3
        assert subject.vertical_anchor < 0.4


class TestSplitScreen:
    """When more than one person is in the conversation, both go on screen."""

    @staticmethod
    def _two_faces(rows: int = 40):  # type: ignore[no-untyped-def]
        import numpy as np

        left = (60, 60, 60, 60)
        right = (340, 60, 60, 60)
        motion = np.zeros((rows, _SAMPLE_HEIGHT, _SAMPLE_WIDTH), dtype=np.uint8)
        tracks = [
            [(row, left) for row in range(0, rows, 4)],
            [(row, right) for row in range(0, rows, 4)],
        ]
        return tracks, motion

    def test_two_people_talking_share_the_screen(self) -> None:
        tracks, motion = self._two_faces()
        motion[:, 95:130, 70:110] = 120   # left speaker's mouth
        motion[:, 95:130, 350:390] = 100  # right speaker's mouth

        speakers = _conversation(tracks, motion, 0, 40)

        assert len(speakers) == 2

    def test_a_face_that_never_moves_is_not_in_the_conversation(self) -> None:
        """A poster on the wall, a photo, somebody asleep -- in the shot,
        but not someone to give half the screen to."""

        tracks, motion = self._two_faces()
        motion[:, 95:130, 70:110] = 120

        assert _conversation(tracks, motion, 0, 40) == []

    def test_a_monologue_with_a_listener_stays_on_the_talker(self) -> None:
        tracks, motion = self._two_faces()
        motion[:, 95:130, 70:110] = 200
        motion[:, 95:130, 350:390] = 20  # the odd nod, well under the talker

        assert _conversation(tracks, motion, 0, 40) == []

    def test_only_one_face_is_never_a_split(self) -> None:
        tracks, motion = self._two_faces()
        motion[:, 95:130, 70:110] = 120

        assert _conversation(tracks[:1], motion, 0, 40) == []

    def test_panes_are_stacked_in_the_order_people_sit(self) -> None:
        left = _face_subject((60, 60, 60, 60))
        right = _face_subject((340, 60, 60, 60))

        split = _split_framing(
            [(0.0, 12.0, [right, left])], 1920, 1080, 1080, 1920
        )

        assert split is not None
        assert split.pane_count == 2
        top, bottom = split.sections[0].panes
        assert top.x < bottom.x, "the person on the left belongs on top"

    def test_a_pane_is_wider_and_shorter_than_the_single_window(self) -> None:
        """Each pane fills the width and half the height, so it carries
        twice the canvas aspect -- not the full-frame 9:16."""

        speaker = _face_subject((160, 60, 60, 60))

        split = _split_framing([(0.0, 12.0, [speaker, speaker])], 1920, 1080, 1080, 1920)

        assert split is not None
        pane_ratio = split.crop_width / split.crop_height
        assert pane_ratio == pytest.approx(1080 / 960, rel=0.02)

    def test_a_flash_of_two_speakers_is_not_worth_splitting_for(self) -> None:
        speaker = _face_subject((160, 60, 60, 60))

        assert (
            _split_framing([(0.0, 0.8, [speaker, speaker])], 1920, 1080, 1080, 1920)
            is None
        )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg binary not available"
)
class TestSpeakerDetection:
    def test_crop_follows_a_speaker_on_the_right(self, tmp_path: Path) -> None:
        source = tmp_path / "right.mp4"
        _make_source_with_speaker_at(source, x=940)

        framing = compute_speaker_framing(str(source), 0.0, 3.0, 1080, 1920)

        assert framing is not None, "no subject found in footage with one speaker"
        window = framing.windows[0]
        # The speaker sits at x 940-1180 of 1280; a centre crop would land
        # at 438 and miss them entirely.
        assert _contains(framing, window, (940, 250, 1180, 470)), (
            f"speaker not inside the crop window {window} of size "
            f"{framing.crop_width}x{framing.crop_height}"
        )

    def test_crop_follows_a_speaker_on_the_left(self, tmp_path: Path) -> None:
        source = tmp_path / "left.mp4"
        _make_source_with_speaker_at(source, x=100)

        framing = compute_speaker_framing(str(source), 0.0, 3.0, 1080, 1920)

        assert framing is not None
        assert _contains(framing, framing.windows[0], (100, 250, 340, 470))

    def test_a_small_speaker_is_zoomed_into_not_left_in_a_full_height_strip(
        self, tmp_path: Path
    ) -> None:
        """The case the naive crop gets wrong: a screen recording whose
        speaker is a webcam bubble in the corner. Cropping a full-height
        strip through the bubble fills most of the short with dark editor;
        the window has to close in on the person."""

        source = tmp_path / "screen_recording.mp4"
        _make_screen_recording_with_webcam(source, face_x=1500, face_y=700)

        framing = compute_speaker_framing(str(source), 0.0, 6.0, 1080, 1920)

        assert framing is not None
        window = framing.windows[0]
        assert _contains(framing, window, (1500, 730, 1760, 950)), (
            f"webcam speaker not inside the crop window {window} of size "
            f"{framing.crop_width}x{framing.crop_height}"
        )
        # The bubble is ~24% of the frame height; a full-height crop would
        # leave it a fifth of the short.
        assert framing.crop_height < framing.source_height, (
            "a full-height crop means the speaker was never zoomed into"
        )
        # The busiest region on screen -- the churning editor pane at
        # x 120-1020 -- must not be what got framed.
        assert window.x > 1020, "framed the editor pane instead of the speaker"

    def test_greyscale_footage_falls_back_to_motion(self, tmp_path: Path) -> None:
        """No chroma to read means no skin test; the moving region is still
        the subject."""

        source = tmp_path / "greyscale.mp4"
        _make_greyscale_source_with_motion_at(source, x=940)

        framing = compute_speaker_framing(str(source), 0.0, 3.0, 1080, 1920)

        assert framing is not None
        window = framing.windows[0]
        centre = window.x + framing.crop_width / 2
        assert 940 <= centre <= 1180, f"crop centred at {centre}, off the subject"

    def test_crop_steps_at_a_cut_between_two_speakers(self, tmp_path: Path) -> None:
        """An interview cutting between two people must reframe at the cut,
        not average them into a crop that misses both."""

        source = _make_two_speaker_interview(tmp_path)

        framing = compute_speaker_framing(str(source), 0.0, 6.0, 1080, 1920)

        assert framing is not None
        assert len(framing.windows) > 1, "no reframe at the cut"
        assert framing.windows[1].start_time > 0
        assert min(window.x for window in framing.windows) < 300
        assert max(window.x for window in framing.windows) > 640

    def test_crop_arguments_carry_the_steps_as_ffmpeg_expressions(
        self, tmp_path: Path
    ) -> None:
        source = _make_two_speaker_interview(tmp_path)

        crop = compute_speaker_crop(str(source), 0.0, 6.0, 1080, 1920)

        assert crop is not None
        crop_width, crop_height, x_expression, y_expression = crop
        assert crop_width > 0 and crop_height > 0
        assert x_expression.startswith("if(lt(t,"), x_expression
        # Both axes come back as strings ffmpeg's `crop` can take as-is --
        # a constant or a stepped expression, never None.
        assert isinstance(y_expression, str) and y_expression

    def test_a_source_already_taller_than_9x16_is_left_alone(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "vertical.mp4"
        _make_source_with_speaker_at(source, x=100, width=720, height=1280)

        assert compute_speaker_framing(str(source), 0.0, 3.0, 1080, 1920) is None

    def test_footage_with_no_localised_subject_declines_to_guess(
        self, tmp_path: Path
    ) -> None:
        """Full-frame noise has no subject; the caller must fall back to
        blurred-fill framing rather than crop somewhere arbitrary."""

        source = tmp_path / "noise.mp4"
        source.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=gray:s=1280x720:r=25:d=3",
                "-vf",
                "noise=alls=90:allf=t+u",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(source),
            ],
            check=True,
            capture_output=True,
        )

        assert compute_speaker_framing(str(source), 0.0, 3.0, 1080, 1920) is None
