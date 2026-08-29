"""Custom application exceptions and their FastAPI exception handlers.

Business logic (services, routers) should raise these instead of raising
`fastapi.HTTPException` directly, so error handling stays consistent and
centralized. Register the handlers below on the FastAPI app in main.py.
"""

from __future__ import annotations

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Base class for all custom application exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "APP_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(AppException):
    """Raised when an operation conflicts with existing state (e.g. duplicate email)."""

    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class UnauthorizedError(AppException):
    """Raised when authentication is missing or invalid."""

    def __init__(self, message: str = "Not authenticated") -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppException):
    """Raised when the authenticated user lacks permission for the action."""

    def __init__(self, message: str = "Not authorized to perform this action") -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ValidationAppError(AppException):
    """Raised for domain-level validation failures outside of Pydantic schema validation."""

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=getattr(
                status,
                "HTTP_422_UNPROCESSABLE_CONTENT",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ),
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle any AppException subclass with a consistent JSON error shape."""

    logger.warning(
        "AppException handled: code=%s status=%s path=%s message=%s",
        exc.code,
        exc.status_code,
        request.url.path,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions so responses never leak stack traces."""

    logger.error(
        "Unhandled exception on path=%s: %s", request.url.path, exc, exc_info=exc
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
    )
