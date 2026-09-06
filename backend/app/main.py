"""FastAPI application entrypoint.

Wires together CORS, global exception handlers, the liveness/readiness
probes, and every API router under the /api/v1 prefix.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
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
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length", "Accept-Ranges", "Content-Type"],
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
    """Liveness probe: the process is up and serving.

    Deliberately dependency-free so an orchestrator doesn't restart a
    healthy API just because the database blipped -- that's what /ready is
    for.
    """

    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness probe: the API can actually serve traffic.

    Checks the database round-trips, and (when a queue is configured) that
    Redis is reachable -- without it, exports would be accepted and then
    never rendered. Returns 503 so a load balancer takes the instance out
    of rotation instead of sending it doomed requests.
    """

    checks: dict[str, str] = {}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("Readiness check failed for database: %s", exc)
        checks["database"] = "unavailable"

    if settings.REDIS_URL:
        try:
            import redis

            redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
            checks["queue"] = "ok"
        except Exception as exc:
            logger.warning("Readiness check failed for redis: %s", exc)
            checks["queue"] = "unavailable"

    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "degraded", "checks": checks},
    )
