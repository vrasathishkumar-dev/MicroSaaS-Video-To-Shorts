"""Clip library endpoints: generation, CRUD, and reordering.

Owned by BACKEND-AGENT. Sub-paths /clips/{id}/broll and /clips/{id}/export
are owned by the B-roll and Export teams respectively and are not defined
here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.clip import Clip
from app.schemas.clip import (
    ClipGenerateRequest,
    ClipReorderRequest,
    ClipResponse,
    ClipUpdateRequest,
    PaginatedClips,
)
from app.services import clip_service

router = APIRouter(prefix="/clips", tags=["clips"])


@router.post(
    "/generate", response_model=list[ClipResponse], status_code=status.HTTP_201_CREATED
)
async def generate_clips(
    payload: ClipGenerateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> list[Clip]:
    """Create draft clips from a video project's highlighted transcript segments."""

    clips = clip_service.create_clips_from_highlights(
        db, video_project_id=payload.video_project_id, user_id=current_user.id
    )
    return clips


@router.get("", response_model=PaginatedClips)
async def list_clips(
    video_project_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> PaginatedClips:
    """List the current user's clips, optionally filtered by video_project_id."""

    items, total = clip_service.list_clips(
        db,
        user_id=current_user.id,
        video_project_id=video_project_id,
        page=page,
        page_size=page_size,
    )
    # pydantic's from_attributes on ClipResponse converts each ORM Clip here.
    return PaginatedClips(items=items, total=total, page=page, page_size=page_size)  # type: ignore[arg-type]


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Clip:
    """Fetch a single clip owned by the current user."""

    return clip_service.get_clip_owned(db, clip_id=clip_id, user_id=current_user.id)


@router.put("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: int,
    payload: ClipUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Clip:
    """Partially update a clip's title, trim times, or caption text."""

    clip = clip_service.get_clip_owned(db, clip_id=clip_id, user_id=current_user.id)
    return clip_service.update_clip(db, clip, payload)


@router.patch("/{clip_id}/reorder", response_model=ClipResponse)
async def reorder_clip(
    clip_id: int,
    payload: ClipReorderRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> Clip:
    """Update a clip's position among siblings in the same video project."""

    clip = clip_service.get_clip_owned(db, clip_id=clip_id, user_id=current_user.id)
    return clip_service.reorder_clip(db, clip, payload.order_index)


@router.delete("/{clip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clip(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Delete a clip. Cascades to its broll_assets."""

    clip = clip_service.get_clip_owned(db, clip_id=clip_id, user_id=current_user.id)
    clip_service.delete_clip(db, clip)
