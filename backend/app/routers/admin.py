"""Admin panel endpoints: user management and platform-wide stats.

Owned by BACKEND-AGENT (admin module). All routes here are gated by the
locally-defined `require_admin` dependency (not the shared `get_current_user`
directly) — only users with `is_admin=True` may access anything under
`/admin`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.models.clip import Clip
from app.models.user import User
from app.models.video_project import VideoProject
from app.schemas.admin import (
    AdminStatsResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    PaginatedAdminUsers,
)

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Gate access to admin-only routes.

    Resolves the authenticated user via the shared `get_current_user`
    dependency, then enforces `is_admin=True`. Raises ForbiddenError for any
    authenticated but non-admin user. This is a local guard — it does not
    modify the shared app.dependencies module.
    """

    if not user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return user


@router.get("/users", response_model=PaginatedAdminUsers)
async def list_users(
    q: str | None = Query(default=None, description="Search by email or full name substring"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> PaginatedAdminUsers:
    """List all users on the platform, paginated, with optional search."""

    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.email.ilike(like), User.full_name.ilike(like)))

    total = query.with_entities(func.count(User.id)).scalar() or 0
    items = (
        query.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
    )
    # pydantic's from_attributes on AdminUserResponse converts each ORM User here.
    return PaginatedAdminUsers(  # type: ignore[arg-type]
        items=items, total=total, page=page, page_size=page_size
    )


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    """Activate or deactivate a user account.

    An admin cannot deactivate their own account (guards against an admin
    accidentally locking themselves out).
    """

    if user_id == admin.id and payload.is_active is False:
        raise ValidationAppError("You cannot deactivate your own account")

    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise NotFoundError("User")

    if payload.is_active is not None:
        target.is_active = payload.is_active

    db.commit()
    db.refresh(target)
    return target


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> AdminStatsResponse:
    """Platform-wide aggregate counts for the admin dashboard.

    All counts are computed via SQL aggregation (func.count), not Python
    loops. See AdminStatsResponse for the active_users_last_30_days
    approximation caveat.
    """

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_videos = db.query(func.count(VideoProject.id)).scalar() or 0
    total_clips = db.query(func.count(Clip.id)).scalar() or 0
    active_users_last_30_days = (
        db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    )

    return AdminStatsResponse(
        total_users=total_users,
        total_videos=total_videos,
        total_clips=total_clips,
        active_users_last_30_days=active_users_last_30_days,
    )
