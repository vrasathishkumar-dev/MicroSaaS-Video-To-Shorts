"""Pydantic schemas for the B-roll sourcing module."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.broll_asset import BrollSource


class BrollAssetResponse(BaseModel):
    """Full representation of a BrollAsset returned to clients."""

    id: int
    clip_id: int
    source: BrollSource
    source_asset_id: str
    asset_url: str
    keyword: str
    position_start: float
    position_end: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrollSearchResult(BaseModel):
    """A single normalized search result from a stock footage provider.

    Same shape produced by `app.services.broll_sourcing.search_pexels` /
    `search_pixabay` — not yet persisted as a BrollAsset.

    Everything past `keyword` is presentation metadata for the clip
    editor's search grid: a poster still and a small preview rendition so
    browsing results doesn't stream a full-resolution file per tile, the
    dimensions and length the user needs to judge a clip before inserting
    it, and the provider page/author both Pexels and Pixabay ask to be
    credited by. All optional — a provider that omits one shouldn't drop
    an otherwise usable result.
    """

    source: BrollSource
    source_asset_id: str
    asset_url: str
    keyword: str
    preview_url: str | None = None
    thumbnail_url: str | None = None
    description: str | None = None
    provider_url: str | None = None
    author: str | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None


class BrollInsertRequest(BaseModel):
    """Request body to manually attach a B-roll asset to a clip."""

    source: BrollSource
    source_asset_id: str = Field(min_length=1, max_length=255)
    asset_url: str = Field(min_length=1, max_length=2048)
    keyword: str = Field(min_length=1, max_length=255)
    position_start: float = Field(ge=0)
    position_end: float = Field(ge=0)

    @field_validator("asset_url")
    @classmethod
    def _asset_url_must_be_http(cls, value: str) -> str:
        """Reject anything but http(s) URLs.

        BrollAsset.asset_url is client-supplied and, at render time,
        video_render._resolve_broll_path() treats any non-http(s)
        string as a candidate local filesystem path. Without this check, a
        user could insert an arbitrary local path (e.g. another user's
        uploaded video under UPLOAD_ROOT) and have it composited into their
        own export — a cross-tenant file disclosure. B-roll is only ever
        legitimately sourced from Pexels/Pixabay, both of which return
        http(s) URLs, so this is not a functional restriction.
        """
        if not value.startswith(("http://", "https://")):
            raise ValueError("asset_url must be an http(s) URL")
        return value

    @model_validator(mode="after")
    def _position_end_after_start(self) -> "BrollInsertRequest":
        """Reject a zero/negative-length window before it reaches the DB.

        video_render silently skips a BrollAsset whose window collapses
        this way, so a bad request would otherwise insert a row that never
        renders instead of failing where the mistake was made.
        """
        if self.position_end <= self.position_start:
            raise ValueError("position_end must be after position_start")
        return self
