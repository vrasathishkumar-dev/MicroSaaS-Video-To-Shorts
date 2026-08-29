"""Pydantic schemas for the admin panel module.

Owned by BACKEND-AGENT (admin module). Consumed by app.routers.admin only.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserResponse(BaseModel):
    """Representation of a User as seen by an admin."""

    id: int
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdateRequest(BaseModel):
    """Admin-driven update payload for a user account.

    Currently supports activating/deactivating an account. Other fields
    (email, password, role) are intentionally not editable through this
    endpoint.
    """

    is_active: bool | None = None


class AdminStatsResponse(BaseModel):
    """Platform-wide aggregate counts for the admin dashboard.

    NOTE on active_users_last_30_days: the User model does not currently
    track a last-login or last-seen timestamp, so there is no way to compute
    genuine 30-day activity. As a best-effort approximation, this field
    counts users where `is_active` is True (i.e. accounts not deactivated
    by an admin), NOT users who logged in or were active within 30 days.
    This should be replaced with a real last-seen-based calculation once
    that tracking exists.
    """

    total_users: int
    total_videos: int
    total_clips: int
    active_users_last_30_days: int


class PaginatedAdminUsers(BaseModel):
    """Paginated envelope for the admin user list."""

    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int
