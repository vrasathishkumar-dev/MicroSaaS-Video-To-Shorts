"""Clip model."""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.broll_asset import BrollAsset
    from app.models.user import User
    from app.models.video_project import VideoProject


class ClipStatus(str, enum.Enum):
    """Render/lifecycle status of a clip."""

    draft = "draft"
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


class ClipFraming(str, enum.Enum):
    """How the clip fills the 9:16 canvas, as chosen in the editor.

    The editor's vocabulary, not ffmpeg's: `speaker_focus` crops to
    whoever is talking (splitting the screen where two people are in
    conversation), `dynamic_blur` fits the whole frame over a blurred fill,
    and `fit` letterboxes it. app.services.video_render maps these onto its
    own framing modes.
    """

    speaker_focus = "speaker_focus"
    dynamic_blur = "dynamic_blur"
    fit = "fit"


class ClipCaptionStyle(str, enum.Enum):
    """Which caption look burns into the export."""

    hormozi = "hormozi"
    neon = "neon"
    bold_box = "bold_box"
    karaoke = "karaoke"
    minimal = "minimal"


class BrollPlacement(str, enum.Enum):
    """Where B-roll sits on screen relative to the main footage.

    One choice for the whole clip -- every attached BrollAsset renders in
    this spot, the same way `framing_mode` is one choice for the whole
    clip rather than per shot. `bottom_right` is a small bordered
    picture-in-picture card (today's only look, kept as the default so
    existing clips render unchanged); `top`/`bottom` are a full-width band
    across that third of the frame; `split` is an even half-and-half stack
    with the main video in the other half.
    """

    bottom_right = "bottom_right"
    top = "top"
    bottom = "bottom"
    split = "split"


class Clip(Base, TimestampMixin):
    """A short, vertical clip generated from a VideoProject."""

    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    video_project_id: Mapped[int] = mapped_column(
        ForeignKey("video_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ClipStatus] = mapped_column(
        Enum(ClipStatus, name="clip_status"), default=ClipStatus.draft, nullable=False
    )
    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Editor choices that the export has to honour -- a clip rendered with
    # framing or captions the user didn't pick is a bug they can see.
    framing_mode: Mapped[ClipFraming] = mapped_column(
        Enum(ClipFraming, name="clip_framing"),
        default=ClipFraming.speaker_focus,
        server_default=ClipFraming.speaker_focus.value,
        nullable=False,
    )
    caption_style: Mapped[ClipCaptionStyle] = mapped_column(
        Enum(ClipCaptionStyle, name="clip_caption_style"),
        default=ClipCaptionStyle.hormozi,
        server_default=ClipCaptionStyle.hormozi.value,
        nullable=False,
    )
    broll_placement: Mapped[BrollPlacement] = mapped_column(
        Enum(BrollPlacement, name="broll_placement"),
        default=BrollPlacement.bottom_right,
        server_default=BrollPlacement.bottom_right.value,
        nullable=False,
    )
    video_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Server-computed virality scoring (see backlog: "Clip virality score is
    # fake"). NULL is a real, distinct state -- never coerced to 0 -- so no
    # server_default: legacy pre-migration rows stay NULL until the scoring
    # service (backend-agent's work, not this model) populates them on the
    # clip's next edit or render. `framing_score` is nullable *and* a
    # pass/fail signal, not a gradient: null = not yet checked (draft, or a
    # failed render left it stale/invalidated), 1.0 = compute_speaker_framing
    # returned a SpeakerFraming, 0.0 = it returned None (checked, no
    # confident subject found). See handoff for how this maps to the
    # Designer's "Confirmed / Not confident / Not checked" three states.
    virality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hook_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completeness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    framing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    virality_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    video_project: Mapped[VideoProject] = relationship("VideoProject", back_populates="clips")
    user: Mapped[User] = relationship("User", back_populates="clips")
    broll_assets: Mapped[list[BrollAsset]] = relationship(
        "BrollAsset",
        back_populates="clip",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Clip id={self.id} video_project_id={self.video_project_id} status={self.status}>"
