"""Tests for caption rasterisation (app.services.caption_render).

These cover the path that guarantees subtitles regardless of how the local
ffmpeg was compiled -- the reason it exists is that a build without libass
or libfreetype used to produce a silently uncaptioned Short.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.caption_render import render_caption_images
from app.services.video_render import _caption_font_file

pytestmark = pytest.mark.skipif(
    _caption_font_file() is None, reason="no TrueType font available on this machine"
)

pytest.importorskip("PIL", reason="Pillow is not installed")


WIDTH = 1080
HEIGHT = 1920


def _render(events, tmp_path: Path):  # type: ignore[no-untyped-def]
    return render_caption_images(events, tmp_path, WIDTH, HEIGHT, _caption_font_file())


class TestRenderCaptionImages:
    def test_one_image_per_caption_carrying_its_own_timing(self, tmp_path: Path) -> None:
        events = [(0.0, 1.5, "First caption"), (1.5, 3.0, "Second caption")]

        images = _render(events, tmp_path)

        assert images is not None
        assert len(images) == 2
        assert [(image.start, image.end) for image in images] == [(0.0, 1.5), (1.5, 3.0)]
        for image in images:
            assert image.path.is_file()
            assert image.path.stat().st_size > 0

    def test_images_are_frame_width_and_sit_above_the_shorts_ui(
        self, tmp_path: Path
    ) -> None:
        from PIL import Image

        images = _render([(0.0, 2.0, "Held clear of the bottom")], tmp_path)

        assert images is not None
        image = images[0]
        with Image.open(image.path) as rendered:
            assert rendered.width == WIDTH
            assert rendered.mode == "RGBA"
            block_height = rendered.height

        # Fully on-screen, and clear of the bottom sixth where YouTube puts
        # the title, channel name and action buttons.
        assert image.y > 0
        assert image.y + block_height <= HEIGHT
        assert image.y + block_height < HEIGHT * 0.9

    def test_text_is_actually_drawn(self, tmp_path: Path) -> None:
        """A transparent PNG would render as no subtitle at all, which is
        exactly the failure this module exists to prevent."""

        from PIL import Image

        images = _render([(0.0, 2.0, "Visible text")], tmp_path)

        assert images is not None
        with Image.open(images[0].path) as rendered:
            alpha = rendered.getchannel("A")
        assert alpha.getextrema()[1] > 0, "the caption image is fully transparent"

    def test_long_text_wraps_instead_of_running_off_the_frame(
        self, tmp_path: Path
    ) -> None:
        from PIL import Image

        short = _render([(0.0, 2.0, "Short")], tmp_path)
        long_dir = tmp_path / "long"
        long_dir.mkdir()
        long = _render(
            [(0.0, 2.0, "A considerably longer caption that cannot fit on one line")],
            long_dir,
        )

        assert short is not None and long is not None
        with Image.open(short[0].path) as short_image, Image.open(long[0].path) as long_image:
            assert long_image.height > short_image.height, "long text did not wrap"
            assert long_image.width == WIDTH

    def test_no_events_produces_no_images(self, tmp_path: Path) -> None:
        assert _render([], tmp_path) == []

    def test_missing_font_falls_back_rather_than_crashing(self, tmp_path: Path) -> None:
        """Returning None lets the caller try ffmpeg's own text filters."""

        assert render_caption_images(
            [(0.0, 1.0, "text")], tmp_path, WIDTH, HEIGHT, None
        ) is None
