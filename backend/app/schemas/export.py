"""Pydantic schemas for the Export & Publish module."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.clip import ClipStatus


class ExportStatusResponse(BaseModel):
    """Current render/export status of a clip.

    Returned by both POST /clips/{id}/export (immediately, status=rendering)
    and GET /clips/{id}/export/status (polled by the frontend until the
    status settles to `ready` or `failed`).
    """

    clip_id: int
    status: ClipStatus
    video_file_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SpeakerFocusWindow(BaseModel):
    """One crop window, as fractions (0-1) of the source frame.

    Normalised rather than in pixels so the editor can apply it to a
    preview element of any size without knowing the source resolution.
    """

    start_time: float
    x: float
    y: float
    width: float
    height: float


class SplitScreenSection(BaseModel):
    """A stretch of the clip shown as stacked panes, one per speaker.

    `panes` are top-to-bottom and each carries its own crop window, in the
    same normalised source coordinates as the single-speaker windows. A
    pane fills the full width and `1 / len(panes)` of the height.
    """

    start_time: float
    end_time: float
    panes: list[SpeakerFocusWindow]


class ClipFramingResponse(BaseModel):
    """Where the speaker is, for the editor's Speaker Focus preview.

    `mode` says what the caller should do with `windows`:

    - `speaker_focus`: crop the source preview to each window in turn, so
      what the user sees is what the export will render.
    - `rendered`: the clip has already been exported to 9:16 with the
      speaker framed -- show the file as-is, with no further cropping.
    - `unavailable`: no confident subject (or no numpy); the export will
      fall back to blurred-fill framing and so should the preview.

    `split_sections` covers the stretches where more than one person is in
    the conversation: play those as stacked panes instead of `windows`,
    which carries the rest of the clip.
    """

    clip_id: int
    mode: Literal["speaker_focus", "rendered", "unavailable"]
    windows: list[SpeakerFocusWindow] = []
    split_sections: list[SplitScreenSection] = []
