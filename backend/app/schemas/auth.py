"""Pydantic schemas for authentication and user-profile endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for POST /auth/register."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """JSON equivalent of the OAuth2 password-flow login payload.

    POST /auth/login itself uses `OAuth2PasswordRequestForm` (form-encoded
    `username`/`password`), as expected by FastAPI's `OAuth2PasswordBearer`
    tokenUrl convention. This schema is provided for documentation/clients
    that want the equivalent JSON shape.
    """

    email: EmailStr
    password: str


class Token(BaseModel):
    """Access/refresh token pair returned by login and refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Payload for POST /auth/refresh and POST /auth/logout."""

    refresh_token: str


class UserResponse(BaseModel):
    """Public-facing representation of a User."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime


class UserUpdateRequest(BaseModel):
    """Payload for PUT /auth/me — partial profile update."""

    full_name: str | None = Field(default=None, max_length=255)
