"""Caption images: subtitles that burn in on every ffmpeg build.

ffmpeg's own text filters are optional at compile time. `ass`/`subtitles`
needs libass; `drawtext` needs libfreetype. Plenty of real builds -- the
default Homebrew ffmpeg on macOS among them -- ship neither, and when they
are missing the render still succeeds and just silently arrives with no
subtitles at all. For an app whose whole output is captioned Shorts, that
is the wrong failure mode.

So captions are rasterised here instead, with Pillow, into one transparent
PNG per caption, which ffmpeg composites with plain `overlay` -- a filter
every build has. The look is deliberate short-form: heavy weight, white,
thick dark outline so it stays legible over any footage, with a drop shadow
for depth, centred and held clear of the Shorts UI along the bottom edge.

`render_caption_images` returns None if Pillow or a usable font is missing,
so the caller can fall back to libass/drawtext rather than dropping
captions entirely.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Fraction of the frame width text may occupy before it wraps to a new line.
_TEXT_WIDTH_RATIO = 0.86
# Lines per caption. Chunks are short by construction (see video_render's
# _chunk_caption_text); this is a backstop for one very long word run.
_MAX_LINES = 3


class CaptionImage:
    """One rendered caption: when to show it, what to show, and where."""

    __slots__ = ("start", "end", "path", "y")

    def __init__(self, start: float, end: float, path: Path, y: int) -> None:
        self.start = start
        self.end = end
        self.path = path
        #: Top edge of the image on the output canvas, in pixels.
        self.y = y

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CaptionImage [{self.start:.2f}, {self.end:.2f}] y={self.y}>"


def render_caption_images(
    events: list[tuple[float, float, str]],
    output_dir: Path,
    width: int,
    height: int,
    font_file: str | None,
) -> list[CaptionImage] | None:
    """Rasterise each caption to a transparent PNG in `output_dir`.

    Args:
        events: `(start, end, text)` triples, in seconds relative to the clip.
        output_dir: Directory to write the PNGs into (a per-render temp dir).
        width: Output canvas width in pixels.
        height: Output canvas height in pixels.
        font_file: Path to a TrueType font, or None to search for one.

    Returns:
        One CaptionImage per event, or None if Pillow or a usable TrueType
        font is unavailable -- in which case the caller should fall back to
        an ffmpeg-native text filter.
    """

    if not events:
        return []

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning(
            "Pillow is not installed, so captions cannot be rasterised; falling "
            "back to ffmpeg's own text filters"
        )
        return None

    if not font_file:
        logger.warning(
            "No TrueType font found for caption rendering; falling back to "
            "ffmpeg's own text filters"
        )
        return None

    font_size = max(28, int(height * settings.RENDER_CAPTION_SCALE))
    try:
        font = ImageFont.truetype(font_file, font_size)
    except OSError as exc:
        logger.warning("Could not load caption font %r: %s", font_file, exc)
        return None

    stroke_width = max(2, font_size // 10)
    shadow_offset = max(2, font_size // 16)
    line_spacing = int(font_size * 0.22)
    max_text_width = int(width * _TEXT_WIDTH_RATIO)
    bottom_margin = int(height * settings.RENDER_CAPTION_MARGIN_RATIO)

    rendered: list[CaptionImage] = []
    for index, (start, end, text) in enumerate(events):
        display_text = text.upper() if settings.RENDER_CAPTION_UPPERCASE else text
        lines = _wrap(display_text, font, max_text_width)

        line_height = font_size + line_spacing
        block_height = line_height * len(lines) + 2 * (stroke_width + shadow_offset)
        image = Image.new("RGBA", (width, block_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        for line_index, line in enumerate(lines):
            y = stroke_width + line_index * line_height
            # Shadow first, then the stroked text over it.
            draw.text(
                (width / 2 + shadow_offset, y + shadow_offset),
                line,
                font=font,
                fill=(0, 0, 0, 140),
                anchor="ma",
            )
            draw.text(
                (width / 2, y),
                line,
                font=font,
                fill=(255, 255, 255, 255),
                stroke_width=stroke_width,
                stroke_fill=(0, 0, 0, 235),
                anchor="ma",
            )

        path = output_dir / f"caption_{index:04d}.png"
        image.save(path, "PNG")
        rendered.append(
            CaptionImage(
                start=start,
                end=end,
                path=path,
                y=max(0, height - bottom_margin - block_height),
            )
        )

    return rendered


def _wrap(text: str, font, max_width: int) -> list[str]:  # type: ignore[no-untyped-def]
    """Greedily wrap `text` to at most `_MAX_LINES` lines of `max_width` px."""

    words = text.split()
    if not words:
        return [text]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and _text_width(candidate, font) > max_width:
            lines.append(current)
            current = word
            if len(lines) == _MAX_LINES - 1:
                # Last allowed line: take the rest verbatim rather than
                # dropping words off the end of the caption.
                remaining = words[words.index(word) :]
                lines.append(" ".join(remaining))
                return lines
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _text_width(text: str, font) -> int:  # type: ignore[no-untyped-def]
    """Rendered width of `text` in pixels."""

    left, _top, right, _bottom = font.getbbox(text)
    return int(right - left)
