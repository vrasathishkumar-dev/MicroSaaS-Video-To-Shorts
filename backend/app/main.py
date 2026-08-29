"""FastAPI application entrypoint.

Wires together CORS, global exception handlers, the health check, and
(eventually) all API routers. Business-logic routers are added by other
agents in a later phase; the include_router() calls below are placeholders
showing where they will be registered.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
)
from app.routers import admin, auth, broll, clips, dashboard, exports, videos

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers. The AppException handler is intentionally typed
# to its narrower exception class rather than the base `Exception` Starlette's
# stub expects for add_exception_handler's second argument — add_exception_handler's
# first argument guarantees only AppException instances ever reach it.
app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router, prefix="/api/v1")
app.include_router(videos.router, prefix="/api/v1")
app.include_router(clips.router, prefix="/api/v1")
app.include_router(broll.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness/readiness probe."""

    return {"status": "ok"}
