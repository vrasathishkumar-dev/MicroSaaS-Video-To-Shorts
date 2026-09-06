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
# Past this many words a caption is a run of text, not a phrase with a
# beat; highlighting through it costs an overlay per word for no gain.
_MAX_HIGHLIGHT_WORDS = 8


class CaptionStyle:
    """One caption look, as the pixels that make it.

    The presets are the ones the editor offers, so what the user picks in
    the studio is what burns into the short. Everything here is drawn with
    Pillow rather than described to a text filter, which is why each look
    can have its own box, glow or highlight instead of just a colour.
    """

    __slots__ = (
        "fill",
        "stroke",
        "uppercase",
        "box",
        "box_border",
        "glow",
        "highlight",
        "underline",
    )

    def __init__(
        self,
        *,
        fill: tuple[int, int, int, int] = (255, 255, 255, 255),
        stroke: tuple[int, int, int, int] = (0, 0, 0, 235),
        uppercase: bool = False,
        box: tuple[int, int, int, int] | None = None,
        box_border: tuple[int, int, int, int] | None = None,
        glow: tuple[int, int, int, int] | None = None,
        highlight: tuple[int, int, int, int] | None = None,
        underline: tuple[int, int, int, int] | None = None,
    ) -> None:
        #: Text colour.
        self.fill = fill
        #: Outline drawn around every glyph, for legibility over footage.
        self.stroke = stroke
        #: Whether to shout.
        self.uppercase = uppercase
        #: Panel drawn behind the text, or None for text straight on frame.
        self.box = box
        #: Outline around that panel.
        self.box_border = box_border
        #: Colour bloomed around the glyphs (a blurred copy under the text).
        self.glow = glow
        #: Colour of the word being spoken right now, where the caller
        #: passes word timings (see `active_word`).
        self.highlight = highlight
        #: Bar under the text block.
        self.underline = underline


#: The editor's presets. Keys match app.models.clip.ClipCaptionStyle.
CAPTION_STYLES: dict[str, CaptionStyle] = {
    "hormozi": CaptionStyle(
        fill=(255, 230, 0, 255),
        uppercase=True,
        box=(8, 8, 10, 235),
        box_border=(163, 230, 53, 255),
        highlight=(163, 230, 53, 255),
    ),
    "neon": CaptionStyle(
        fill=(34, 211, 238, 255),
        stroke=(8, 20, 30, 235),
        uppercase=True,
        box=(6, 8, 20, 190),
        box_border=(34, 211, 238, 200),
        glow=(34, 211, 238, 150),
        highlight=(232, 121, 249, 255),
    ),
    "bold_box": CaptionStyle(
        box=(10, 10, 12, 200),
    ),
    "karaoke": CaptionStyle(
        fill=(226, 255, 240, 255),
        uppercase=True,
        box=(6, 10, 8, 170),
        underline=(52, 211, 153, 255),
        highlight=(52, 211, 153, 255),
    ),
    "minimal": CaptionStyle(),
}

_DEFAULT_STYLE = CAPTION_STYLES["minimal"]


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
    style: CaptionStyle | str | None = None,
) -> list[CaptionImage] | None:
    """Rasterise each caption to a transparent PNG in `output_dir`.

    Args:
        events: `(start, end, text)` triples, in seconds relative to the clip.
        output_dir: Directory to write the PNGs into (a per-render temp dir).
        width: Output canvas width in pixels.
        height: Output canvas height in pixels.
        font_file: Path to a TrueType font, or None to search for one.
        style: A CaptionStyle, or the name of one of `CAPTION_STYLES` --
            whichever preset the clip was set to in the editor. Defaults to
            the clean minimal look.

    Returns:
        One CaptionImage per event (more, where a style highlights each word
        in turn), or None if Pillow or a usable TrueType font is
        unavailable -- in which case the caller should fall back to an
        ffmpeg-native text filter.
    """

    if not events:
        return []

    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
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

    if isinstance(style, str):
        style = CAPTION_STYLES.get(style, _DEFAULT_STYLE)
    style = style or _DEFAULT_STYLE

    font_size = max(28, int(height * settings.RENDER_CAPTION_SCALE))
    try:
        font = ImageFont.truetype(font_file, font_size)
    except OSError as exc:
        logger.warning("Could not load caption font %r: %s", font_file, exc)
        return None

    stroke_width = max(2, font_size // 10)
    shadow_offset = max(2, font_size // 16)
    line_spacing = int(font_size * 0.22)
    padding = int(font_size * 0.35)
    max_text_width = int(width * _TEXT_WIDTH_RATIO)
    bottom_margin = int(height * settings.RENDER_CAPTION_MARGIN_RATIO)
    space_width = _text_width(" ", font)

    rendered: list[CaptionImage] = []
    for index, (start, end, text, active_word) in enumerate(
        caption_frames(events, style)
    ):
        display_text = text.upper() if style.uppercase else text
        lines = _wrap(display_text, font, max_text_width)

        line_height = font_size + line_spacing
        margin = stroke_width + shadow_offset + padding
        block_height = line_height * len(lines) + 2 * margin
        if style.underline:
            block_height += padding
        image = Image.new("RGBA", (width, block_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        widths = [_text_width(line, font) for line in lines]
        panel_width = max(widths) + 2 * padding
        panel_left = (width - panel_width) / 2
        panel_right = panel_left + panel_width

        if style.box:
            draw.rounded_rectangle(
                (panel_left, stroke_width, panel_right, block_height - stroke_width),
                radius=int(font_size * 0.28),
                fill=style.box,
                outline=style.box_border,
                width=max(2, font_size // 18) if style.box_border else 0,
            )

        # A glow is the same text drawn once onto its own layer, blurred,
        # and laid underneath -- Pillow has no glyph shadow of its own.
        glow_layer = (
            Image.new("RGBA", (width, block_height), (0, 0, 0, 0))
            if style.glow
            else None
        )
        glow_draw = ImageDraw.Draw(glow_layer) if glow_layer is not None else None

        word_index = 0
        for line_index, line in enumerate(lines):
            y = margin + line_index * line_height
            x = (width - widths[line_index]) / 2
            for word in line.split(" "):
                if not word:
                    continue
                fill = (
                    style.highlight
                    if style.highlight is not None and word_index == active_word
                    else style.fill
                )
                if glow_draw is not None:
                    glow_draw.text((x, y), word, font=font, fill=style.glow)
                # Shadow first, then the stroked word over it.
                draw.text(
                    (x + shadow_offset, y + shadow_offset),
                    word,
                    font=font,
                    fill=(0, 0, 0, 140),
                )
                draw.text(
                    (x, y),
                    word,
                    font=font,
                    fill=fill,
                    stroke_width=stroke_width,
                    stroke_fill=style.stroke,
                )
                x += _text_width(word, font) + space_width
                word_index += 1

        if glow_layer is not None:
            glow_layer = glow_layer.filter(
                ImageFilter.GaussianBlur(radius=max(3, font_size // 6))
            )
            image = Image.alpha_composite(glow_layer, image)

        if style.underline:
            bar_height = max(3, font_size // 12)
            bar_top = block_height - margin + padding // 2
            ImageDraw.Draw(image).rounded_rectangle(
                (
                    panel_left + padding,
                    bar_top,
                    panel_right - padding,
                    bar_top + bar_height,
                ),
                radius=bar_height // 2,
                fill=style.underline,
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


def caption_frames(
    events: list[tuple[float, float, str]], style: CaptionStyle | None
) -> list[tuple[float, float, str, int | None]]:
    """Expand captions into the frames to draw, one per event or per word.

    A style with a highlight colour lights up each word as it is spoken,
    which means one image per word rather than per caption. Timings are
    split across the caption's own window in proportion to how long each
    word takes to say -- a decent stand-in for word timings the transcript
    doesn't carry. Very long chunks are left whole: they are usually a run
    of text with no natural rhythm to follow, and expanding them would cost
    an overlay per word for no visible gain.
    """

    if style is None or style.highlight is None:
        return [(start, end, text, None) for start, end, text in events]

    frames: list[tuple[float, float, str, int | None]] = []
    for start, end, text in events:
        words = text.split()
        if len(words) < 2 or len(words) > _MAX_HIGHLIGHT_WORDS:
            frames.append((start, end, text, None))
            continue

        weights = [len(word) + 1 for word in words]
        total = sum(weights)
        elapsed = start
        for index, weight in enumerate(weights):
            share = (end - start) * weight / total
            word_end = end if index == len(weights) - 1 else elapsed + share
            frames.append((elapsed, word_end, text, index))
            elapsed = word_end
    return frames


def _wrap(text: str, font, max_width: int) -> list[str]:  # type: ignore[no-untyped-def]
    """Greedily wrap `text` to lines no wider than `max_width` px.

    No cap on the number of lines: capping used to force any leftover words
    onto one final, unmeasured line, which could run wider than the frame
    and get clipped at both edges. A single word that alone exceeds
    `max_width` still overflows -- there's no narrower way to draw it.
    """

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
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _text_width(text: str, font) -> int:  # type: ignore[no-untyped-def]
    """Rendered width of `text` in pixels."""

    left, _top, right, _bottom = font.getbbox(text)
    return int(right - left)
