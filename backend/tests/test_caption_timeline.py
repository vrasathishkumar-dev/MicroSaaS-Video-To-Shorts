"""Tests for the burned-in caption timeline (app.services.video_render).

These are pure timeline/formatting logic and need no ffmpeg binary, unlike
the end-to-end render tests in test_video_render.py.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.video_render import (
    _ass_timestamp,
    _caption_events,
    _chunk_caption_text,
    _write_ass_file,
)


def _segment(start: float, end: float, text: str) -> SimpleNamespace:
    """A stand-in for a TranscriptSegment row (only these fields are read)."""

    return SimpleNamespace(start_time=start, end_time=end, text=text)


class TestChunkCaptionText:
    def test_splits_long_text_into_readable_chunks(self) -> None:
        text = (
            "Here is the single most important mistake that ninety nine percent "
            "of people make when they are starting out"
        )
        chunks = _chunk_caption_text(text)

        assert len(chunks) > 1
        assert all(len(chunk) <= 30 for chunk in chunks), chunks
        assert " ".join(chunks) == text, "chunking must not drop or reorder words"

    def test_short_text_stays_a_single_chunk(self) -> None:
        assert _chunk_caption_text("Watch this") == ["Watch this"]

    def test_a_single_overlong_word_is_kept_whole(self) -> None:
        word = "supercalifragilisticexpialidocious"
        assert _chunk_caption_text(word) == [word]


class TestCaptionEvents:
    def test_transcript_segments_are_retimed_to_the_clip_timeline(self) -> None:
        segments = [
            _segment(0.0, 10.0, "Before the clip starts"),
            _segment(30.0, 36.0, "This lands inside the clip window"),
            _segment(90.0, 95.0, "Well after the clip ends"),
        ]

        events = _caption_events(
            caption_text=None,
            transcript_segments=segments,
            clip_start=28.0,
            duration=12.0,
        )

        assert events, "the overlapping segment produced no captions"
        # Times are relative to the export (0 = clip start), never absolute.
        assert all(0.0 <= start < end <= 12.0 for start, end, _ in events)
        rendered = " ".join(text for _, _, text in events)
        assert rendered == "This lands inside the clip window"

    def test_segments_are_clamped_to_the_clip_window(self) -> None:
        segments = [_segment(5.0, 40.0, "A segment that overruns both ends")]

        events = _caption_events(
            caption_text=None,
            transcript_segments=segments,
            clip_start=10.0,
            duration=8.0,
        )

        assert events
        assert events[0][0] == 0.0
        assert events[-1][1] <= 8.0

    def test_captions_never_overlap_each_other(self) -> None:
        segments = [
            _segment(0.0, 2.0, "One two three four five six seven eight"),
            _segment(2.0, 4.0, "Nine ten eleven twelve thirteen fourteen"),
        ]

        events = _caption_events(
            caption_text=None,
            transcript_segments=segments,
            clip_start=0.0,
            duration=4.0,
        )

        for (_, end, _), (next_start, _, _) in zip(events, events[1:], strict=False):
            assert end <= next_start + 1e-6, "captions overlap on screen"

    def test_user_caption_text_overrides_the_transcript(self) -> None:
        segments = [_segment(0.0, 5.0, "The transcript text")]

        events = _caption_events(
            caption_text="My own hook line for this short",
            transcript_segments=segments,
            clip_start=0.0,
            duration=5.0,
        )

        rendered = " ".join(text for _, _, text in events)
        assert rendered == "My own hook line for this short"
        assert events[0][0] == 0.0
        assert events[-1][1] == 5.0

    def test_no_transcript_and_no_caption_text_yields_no_captions(self) -> None:
        assert (
            _caption_events(
                caption_text=None, transcript_segments=[], clip_start=0.0, duration=10.0
            )
            == []
        )


class TestAssFile:
    def test_timestamps_use_ass_h_mm_ss_cc_format(self) -> None:
        assert _ass_timestamp(0.0) == "0:00:00.00"
        assert _ass_timestamp(65.25) == "0:01:05.25"
        assert _ass_timestamp(3661.5) == "1:01:01.50"

    def test_written_file_has_a_dialogue_line_per_caption(self, tmp_path) -> None:  # noqa: ANN001
        events = [(0.0, 1.5, "First line"), (1.5, 3.0, "Second line")]
        path = tmp_path / "captions.ass"

        _write_ass_file(events, path, 1080, 1920)

        content = path.read_text(encoding="utf-8")
        assert "PlayResX: 1080" in content
        assert "PlayResY: 1920" in content
        assert content.count("\nDialogue: ") == 2
        assert "First line" in content and "Second line" in content

    def test_braces_in_caption_text_cannot_inject_ass_override_tags(
        self, tmp_path  # noqa: ANN001
    ) -> None:
        """`{...}` is ASS's style-override syntax -- transcript text must
        never be able to reposition or restyle the captions."""

        path = tmp_path / "captions.ass"
        _write_ass_file([(0.0, 1.0, "{\\pos(0,0)}hidden")], path, 1080, 1920)

        dialogue = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("Dialogue:")
        ][0]
        assert "{" not in dialogue and "}" not in dialogue
