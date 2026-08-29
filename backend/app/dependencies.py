"""Shared FastAPI dependencies.

get_db() is owned by DATABASE-AGENT (app.database) and simply re-exported
here so routers/services have a single, stable import path. get_current_user()
resolves the authenticated user from a bearer JWT access token.
"""

from __future__ import annotations

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_token

# Re-exported so callers can `from app.dependencies import get_db` without
# needing to know which module owns the database session factory.
from app.database import get_db
from app.exceptions import UnauthorizedError
from app.models.user import User

# tokenUrl is the final registered path (routers get "/api/v1" prefix in main.py).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _resolve_user_from_access_token(token: str | None, db: Session) -> User:
    """Shared token-decoding logic behind get_current_user() and its
    query-param variant used for media elements (see get_current_user_for_media).
    """

    if not token:
        raise UnauthorizedError("Not authenticated")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired access token")

    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Invalid access token")

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        raise UnauthorizedError("Invalid access token") from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the currently authenticated user from a bearer JWT access token.

    Raises UnauthorizedError when the token is missing, malformed, expired,
    not an access token, or does not resolve to an active user.
    """

    return _resolve_user_from_access_token(token, db)


async def get_current_user_for_media(
    token: str | None = None,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current user for HTML `<video>`/`<audio>` element requests.

    Browsers never attach an `Authorization` header for a plain `<video
    src>` load, so media-streaming endpoints (e.g. clip preview) accept the
    access token as a `?token=` query parameter instead. Only use this for
    read-only media byte-streaming endpoints -- everything else should keep
    using get_current_user's header-only Bearer flow.
    """

    return _resolve_user_from_access_token(token, db)
