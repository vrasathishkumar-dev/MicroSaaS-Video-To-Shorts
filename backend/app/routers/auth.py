"""Authentication endpoints: register, login, refresh, logout, profile.

Registered by the orchestrator in main.py with prefix="/api/v1", so the
final paths are /api/v1/auth/*.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.rate_limit import rate_limit_auth
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    RefreshRequest,
    RegisterRequest,
    Token,
    UserResponse,
    UserUpdateRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """Create a new user account."""

    return auth_service.register_user(db, payload)


@router.post(
    "/login",
    response_model=Token,
    dependencies=[Depends(rate_limit_auth)],
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate with email (as `username`) + password, returning a token pair."""

    user = auth_service.authenticate_user(db, form_data.username, form_data.password)
    return auth_service.issue_tokens(db, user)


@router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Exchange a valid refresh token for a new access/refresh token pair."""

    return auth_service.refresh_access_token(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    """Revoke a refresh token, ending the associated session."""

    auth_service.revoke_refresh_token(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    """Return the profile of the currently authenticated user."""

    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update the profile of the currently authenticated user."""

    return auth_service.update_user_profile(db, current_user, payload)
