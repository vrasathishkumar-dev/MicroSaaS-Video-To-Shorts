"""Tests for which moments become shorts (app.services.highlight_detection).

Written against transcripts that look like real speech -- short Whisper
segments, filler at the edges, one moment that is obviously the clippable
one -- because that is the material the scoring has to survive. A scorer
that only works on tidy paragraphs picks the wrong 40 seconds of a talk
show.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.highlight_detection import (
    _filler_penalty,
    calculate_target_shorts_count,
    detect_highlights,
    hook_score,
)


@dataclass
class _Segment:
    """Stand-in for TranscriptSegment: detect_highlights only touches these."""

    start_time: float
    end_time: float
    text: str
    is_highlight: bool = False
    highlight_score: float | None = None


def _transcript(lines: list[tuple[float, float, str]]) -> list[_Segment]:
    return [_Segment(start, end, text) for start, end, text in lines]


class TestHookScoring:
    def test_a_question_opens_better_than_a_statement(self) -> None:
        assert hook_score("So why did nobody tell us this?") > hook_score(
            "And then we drove to the studio."
        )

    def test_a_claim_with_a_number_reads_as_a_hook(self) -> None:
        assert hook_score("I wasted 3 years doing it the wrong way") > 0

    def test_small_talk_is_not_a_hook(self) -> None:
        assert hook_score("Yeah, it was a nice day out there.") == 0.0


class TestFillerPenalty:
    def test_greetings_and_applause_are_penalised(self) -> None:
        assert (
            _filler_penalty(
                "Thank you, thank you so much. Welcome back to the show, "
                "please welcome our guest tonight. [Applause]"
            )
            > 0.5
        )

    def test_an_interjection_is_all_filler(self) -> None:
        assert _filler_penalty("Yeah, right.") == 1.0

    def test_a_real_point_is_not_penalised(self) -> None:
        assert (
            _filler_penalty(
                "The biggest mistake I made was assuming the audience wanted "
                "the polished version of the story rather than the true one."
            )
            == 0.0
        )


class TestHighlightSelection:
    def test_the_clippable_moment_beats_the_opening_pleasantries(self) -> None:
        """A talk show opens with thanks and applause and gets good later.
        Picking the opening is the failure this scoring exists to avoid."""

        segments = _transcript(
            [
                (0.0, 4.0, "Thank you, thank you so much."),
                (4.0, 9.0, "Welcome back to the show, please welcome our guest."),
                (9.0, 14.0, "Hi everybody. Thanks for having me."),
                (14.0, 20.0, "It's so nice to see you, you look great."),
                (20.0, 26.0, "Here's the thing nobody tells you about this job."),
                (
                    26.0,
                    34.0,
                    "The biggest mistake I made was trying to sound like everyone else.",
                ),
                (
                    34.0,
                    45.0,
                    "The truth is it cost me three years before I realized "
                    "an audience can always tell when you mean it.",
                ),
                (45.0, 52.0, "And that changed how I picked every role after that."),
            ]
        )

        detect_highlights(segments)  # type: ignore[arg-type]

        best = max(segments, key=lambda s: s.highlight_score or 0.0)
        assert best.start_time >= 20.0, (
            f"picked {best.text!r} over the actual moment"
        )
        # The applause at the top still opens a window that contains the
        # good part later on, so it isn't zero -- it just has to be nowhere
        # near the moment that actually opens with a hook.
        assert (segments[0].highlight_score or 0) < (best.highlight_score or 0) / 2

    def test_a_silent_stretch_scores_below_speech(self) -> None:
        """Whisper leaves long, near-empty segments over music and pauses.
        Density is what keeps those out of the shorts."""

        segments = _transcript(
            [
                (0.0, 40.0, "Okay. So."),
                (
                    40.0,
                    48.0,
                    "The reason this works is that you commit to one idea and "
                    "you let the rest of it go, which is harder than it sounds.",
                ),
            ]
        )

        detect_highlights(segments)  # type: ignore[arg-type]

        assert (segments[1].highlight_score or 0) > (segments[0].highlight_score or 0)

    def test_every_segment_is_scored_and_something_is_always_picked(self) -> None:
        segments = _transcript(
            [(float(i) * 5, float(i) * 5 + 5, f"Line number {i} of the talk.") for i in range(12)]
        )

        detect_highlights(segments)  # type: ignore[arg-type]

        assert all(segment.highlight_score is not None for segment in segments)
        assert any(segment.is_highlight for segment in segments)

    def test_highlights_are_spread_across_a_long_video(self) -> None:
        """All five shorts coming from the same two minutes would waste an
        hour-long source."""

        segments = _transcript(
            [
                (
                    float(i) * 30,
                    float(i) * 30 + 28,
                    f"Here's the thing nobody tells you about part {i}. "
                    "The biggest mistake is assuming it stays the same forever.",
                )
                for i in range(40)
            ]
        )

        detect_highlights(segments)  # type: ignore[arg-type]

        picked = [s for s in segments if s.is_highlight]
        assert len(picked) > 1
        spread = picked[-1].start_time - picked[0].start_time
        assert spread > 300, f"highlights bunched into {spread:.0f}s of a 20min video"


class TestTargetCount:
    def test_a_one_minute_video_yields_a_single_short(self) -> None:
        assert calculate_target_shorts_count(45.0) == 1

    def test_a_longer_video_yields_more(self) -> None:
        assert calculate_target_shorts_count(600.0) > calculate_target_shorts_count(180.0)
