"""Business logic for authentication: registration, login, and token lifecycle."""

from __future__ import annotations

import logging as _logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings
from app.exceptions import ConflictError, UnauthorizedError
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest, Token, UserUpdateRequest


def register_user(db: Session, payload: RegisterRequest) -> User:
    """Create a new user, raising ConflictError if the email is already taken."""

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise ConflictError("An account with this email already exists")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Validate credentials, raising UnauthorizedError on any failure.

    Returns the same generic error for "no such user" and "wrong password"
    so the endpoint doesn't leak whether an email is registered.
    """

    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is inactive")
    return user


def issue_tokens(db: Session, user: User) -> Token:
    """Create an access/refresh token pair and persist the refresh token."""

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    expires_at = datetime.now(UTC) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    db.add(
        RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
            revoked=False,
        )
    )
    db.commit()

    return Token(access_token=access_token, refresh_token=refresh_token)


def refresh_access_token(db: Session, refresh_token: str) -> Token:
    """Validate a refresh token against the DB and issue a rotated token pair.

    The presented refresh token is revoked once used (rotation), and a new
    access/refresh pair is issued and persisted in its place.
    """

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid refresh token")

    stored = (
        db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    )
    if stored is None or stored.revoked:
        raise UnauthorizedError("Refresh token has been revoked or does not exist")

    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise UnauthorizedError("Refresh token has expired")

    user = db.query(User).filter(User.id == stored.user_id).first()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    # Rotate: revoke the used refresh token before issuing a new pair.
    stored.revoked = True
    db.commit()

    return issue_tokens(db, user)


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a refresh token (logout). No-op if the token doesn't exist."""

    stored = (
        db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
    )
    if stored is None:
        return
    stored.revoked = True
    db.commit()


def update_user_profile(db: Session, user: User, payload: UserUpdateRequest) -> User:
    """Apply a partial profile update to a user."""

    if payload.full_name is not None:
        user.full_name = payload.full_name
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Password reset (personal-use implementation)
#
# No email infrastructure is required: the reset token is printed to the
# server console (uvicorn stdout). For a single-user personal site this is
# perfectly workable -- you check the terminal, copy the URL, paste it.
# ---------------------------------------------------------------------------

_reset_logger = _logging.getLogger(__name__)

# In-memory token store: {token: (user_id, expiry_timestamp)}.
# Sufficient for personal use (one user, restarts clear old tokens which is
# fine since you'd just request a new one). Replace with a DB table for
# multi-user production use.
_reset_tokens: dict[str, tuple[int, float]] = {}
_RESET_TOKEN_TTL_SECONDS = 3600  # 1 hour


def generate_password_reset_token(db: Session, email: str) -> None:
    """Generate a time-limited reset token and log the reset URL to stdout.

    Returns silently whether or not the email exists, so the endpoint
    never leaks registered addresses.
    """
    import time

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        _reset_logger.info("Password reset requested for unknown email: %s", email)
        return

    token = secrets.token_urlsafe(32)
    _reset_tokens[token] = (user.id, time.time() + _RESET_TOKEN_TTL_SECONDS)

    reset_url = f"http://localhost:5173/reset-password?token={token}"
    _reset_logger.warning(
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  PASSWORD RESET REQUESTED for %s\n"
        "  Open this URL in your browser (valid for 1 hour):\n"
        "  %s\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        email,
        reset_url,
    )


def reset_password(db: Session, token: str, new_password: str) -> None:
    """Validate a reset token and update the user's password.

    Raises UnauthorizedError if the token is missing, expired, or already used.
    """
    import time

    entry = _reset_tokens.get(token)
    if entry is None:
        raise UnauthorizedError("Invalid or expired password reset token")

    user_id, expiry = entry
    if time.time() > expiry:
        del _reset_tokens[token]
        raise UnauthorizedError("Password reset token has expired. Request a new one.")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UnauthorizedError("User no longer exists")

    user.hashed_password = hash_password(new_password)
    db.commit()

    # Invalidate the token after use.
    del _reset_tokens[token]
    _reset_logger.info("Password reset successfully for user id=%s", user_id)
