"""B-roll sourcing endpoints: auto-source, search, manual insert, delete.

Kept as a separate router file from `app.routers.clips` (owned by the Clip
Library team) to avoid touching their file. Paths are nested under
/clips/{clip_id}/broll/... and /broll/search, which don't collide with the
Clip Library router's /clips, /clips/{id}, /clips/{id}/reorder paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.rate_limit import rate_limit_broll
from app.dependencies import get_current_user, get_db
from app.exceptions import NotFoundError
from app.models.broll_asset import BrollAsset, BrollSource
from app.models.clip import Clip
from app.models.user import User
from app.schemas.broll import BrollAssetResponse, BrollInsertRequest, BrollSearchResult
from app.services.broll_sourcing import auto_source_broll, search_pexels, search_pixabay

router = APIRouter(tags=["broll"])


def _get_owned_clip(db: Session, clip_id: int, user: User) -> Clip:
    """Fetch a clip by id and verify it belongs to `user`.

    A local, minimal lookup against the Clip model directly (not the Clip
    Library service) to avoid cross-module coupling.
    """

    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if clip is None or clip.user_id != user.id:
        raise NotFoundError("Clip")
    return clip


@router.get("/clips/{clip_id}/broll", response_model=list[BrollAssetResponse])
async def list_clip_broll(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BrollAsset]:
    """List all B-roll assets attached to a clip."""

    clip = _get_owned_clip(db, clip_id, current_user)
    return (
        db.query(BrollAsset)
        .filter(BrollAsset.clip_id == clip.id)
        .order_by(BrollAsset.position_start.asc())
        .all()
    )


@router.post("/clips/{clip_id}/broll/auto", response_model=list[BrollAssetResponse])
async def auto_source_clip_broll(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BrollAsset]:
    """Automatically source and attach B-roll footage to a clip."""

    rate_limit_broll(current_user.id)
    clip = _get_owned_clip(db, clip_id, current_user)
    return await auto_source_broll(db, clip)


@router.get("/broll/search", response_model=list[BrollSearchResult])
async def search_broll(
    q: str = Query(..., min_length=1),
    source: BrollSource | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Search stock footage providers for `q`. Does not write to the DB.

    Searches both Pexels and Pixabay unless `source` narrows to one.
    """

    rate_limit_broll(current_user.id)

    if source == BrollSource.pexels:
        return await search_pexels(q)
    if source == BrollSource.pixabay:
        return await search_pixabay(q)

    pexels_results = await search_pexels(q)
    pixabay_results = await search_pixabay(q)
    return [*pexels_results, *pixabay_results]


@router.post("/clips/{clip_id}/broll", response_model=BrollAssetResponse)
async def insert_clip_broll(
    clip_id: int,
    payload: BrollInsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BrollAsset:
    """Manually attach a B-roll asset to a clip."""

    clip = _get_owned_clip(db, clip_id, current_user)

    asset = BrollAsset(
        clip_id=clip.id,
        source=payload.source,
        source_asset_id=payload.source_asset_id,
        asset_url=payload.asset_url,
        keyword=payload.keyword,
        position_start=payload.position_start,
        position_end=payload.position_end,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/clips/{clip_id}/broll/{broll_id}", status_code=204)
async def delete_clip_broll(
    clip_id: int,
    broll_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a B-roll asset, verifying it belongs to a clip the user owns."""

    clip = _get_owned_clip(db, clip_id, current_user)

    asset = (
        db.query(BrollAsset)
        .filter(BrollAsset.id == broll_id, BrollAsset.clip_id == clip.id)
        .first()
    )
    if asset is None:
        raise NotFoundError("BrollAsset")

    db.delete(asset)
    db.commit()
