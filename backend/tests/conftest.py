"""Shared pytest fixtures for the backend test suite.

Sets required environment variables *before* importing anything from `app`,
since `app.config.settings` (and `app.database.engine`) are constructed at
import time. Uses an in-memory SQLite database (shared across connections
via StaticPool) instead of a real Postgres instance so the suite is fast and
has no external dependencies, while still exercising real FK-cascade
behavior via `PRAGMA foreign_keys=ON`.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Environment variables MUST be set before importing app.config / app.main,
# since pydantic-settings reads them once at import time.
# ---------------------------------------------------------------------------
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("PEXELS_API_KEY", "test-pexels-key")
os.environ.setdefault("PIXABAY_API_KEY", "test-pixabay-key")
os.environ.setdefault("TRANSCRIPTION_API_KEY", "test-transcription-key")
# Explicitly force these empty (not just setdefault) so a developer's real
# local backend/.env -- which pydantic-settings reads as a lower-priority
# source whenever a key is absent from the actual environment -- can never
# leak a real STORAGE_BUCKET/REDIS_URL into the test run and make tests
# hit real S3/Redis. The suite must stay hermetic regardless of local dev
# config; local disk storage and BackgroundTasks are exercised deliberately
# (see app.services.storage.is_s3_backed() / app.services.task_queue).
os.environ["STORAGE_BUCKET"] = ""
os.environ["REDIS_URL"] = ""

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth.jwt import create_access_token  # noqa: E402
from app.auth.rate_limit import (  # noqa: E402
    _auth_limiter,
    _broll_limiter,
    _video_submit_limiter,
)
from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402
from app.services import auth_service  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """A single in-memory SQLite engine shared across the whole test session.

    StaticPool ensures every connection checkout returns the *same*
    underlying SQLite connection, so the in-memory database persists across
    checkouts (normally each `:memory:` connection is its own separate DB).
    """

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_sqlite_fk(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        """SQLite only enforces FK (and therefore ON DELETE CASCADE) when
        this pragma is set on each connection -- it defaults to OFF."""

        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """A fresh, isolated schema + session for every test.

    Rather than wrapping each test in a rollback-only outer transaction
    (which requires SAVEPOINT gymnastics to survive the app code's own
    `db.commit()` calls), tables are dropped and recreated per test. This is
    simple and reliable, and cheap since the DB is in-memory.
    """

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session, engine: Engine) -> Generator[TestClient, None, None]:
    """A FastAPI TestClient with `get_db` overridden to open a fresh Session
    per request, bound to the same test engine `db_session` uses.

    Deliberately does NOT reuse the single `db_session` object for every
    request (as a naive override might): `db_session` and any background
    task's own session (see `_patch_background_sessionmakers`) already
    commit their own changes independently, and a long-lived Session's
    identity map does *not* refresh already-loaded, unexpired instances
    just because a different Session/connection committed a change to the
    same row. Minting a new Session per request mirrors the real `get_db`
    dependency's behavior and guarantees each request observes the latest
    committed state, exactly like it would against a real Postgres server.
    """

    request_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db() -> Generator[Session, None, None]:
        session = request_sessionmaker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _patch_background_sessionmakers(engine: Engine) -> None:
    """Point background-task modules' own `SessionLocal` at the test engine.

    `process_video_project` (app.routers.videos) and `render_clip`
    (app.services.video_render) each open their *own* fresh DB session via
    a module-level `SessionLocal` imported directly from app.database --
    they do NOT go through the `get_db` FastAPI dependency, so overriding
    `app.dependency_overrides[get_db]` alone does not reach them. Since
    `from app.database import SessionLocal` binds a name in each importing
    module's own namespace, the module-level attribute (not app.database's)
    must be reassigned for the patch to actually take effect.
    """

    import app.database as database_module
    import app.routers.videos as videos_module
    import app.services.video_render as video_render_module

    test_sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    database_module.SessionLocal = test_sessionmaker  # type: ignore[attr-defined]
    videos_module.SessionLocal = test_sessionmaker  # type: ignore[attr-defined]
    video_render_module.SessionLocal = test_sessionmaker  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _isolate_storage_paths(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """Redirect real file writes (uploads, rendered exports) to a per-test
    tmp dir instead of the repo's backend/uploads/, so tests never leave
    artifacts behind or race on shared paths."""

    import app.services.storage as storage_module
    import app.services.video_render as video_render_module

    monkeypatch.setattr(storage_module, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(
        video_render_module, "EXPORTS_DIR", tmp_path / "uploads" / "exports"
    )


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Clear every in-process rate limiter's hit log before every test.

    Without this, these shared process-global sliding-window limiters
    (auth: 5/60s per client IP, video submit: 10/5min per user, broll:
    20/5min per user) would accumulate hits across tests and cause
    unrelated tests to fail with 429s -- especially since dropping and
    recreating tables each test means `test_user`/`admin_user` usually get
    the same id (1) again, reusing the same rate-limit bucket key.
    """

    _auth_limiter._hits.clear()
    _video_submit_limiter._hits.clear()
    _broll_limiter._hits.clear()


@pytest.fixture()
def test_user(db_session: Session) -> User:
    """A regular (non-admin) persisted user, created directly via the
    service layer (bypassing the rate-limited HTTP endpoint)."""

    payload = RegisterRequest(
        email="testuser@example.com", password="TestPass123!", full_name="Test User"
    )
    return auth_service.register_user(db_session, payload)


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Bearer auth header for `test_user`."""

    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_user(db_session: Session) -> User:
    """A second persisted, regular user -- distinct from `test_user` -- for
    exercising cross-user ownership/404 checks with a real FK-valid row
    (SQLite FK enforcement is on, so a fabricated user_id would fail)."""

    payload = RegisterRequest(
        email="otheruser@example.com", password="OtherPass123!", full_name="Other User"
    )
    return auth_service.register_user(db_session, payload)


@pytest.fixture()
def admin_user(db_session: Session) -> User:
    """A persisted user with `is_admin=True` set directly on the row (the
    register endpoint has no way to grant admin)."""

    payload = RegisterRequest(
        email="admin@example.com", password="AdminPass123!", full_name="Admin User"
    )
    user = auth_service.register_user(db_session, payload)
    user.is_admin = True
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_headers(admin_user: User) -> dict[str, str]:
    """Bearer auth header for `admin_user`."""

    token = create_access_token({"sub": str(admin_user.id)})
    return {"Authorization": f"Bearer {token}"}
