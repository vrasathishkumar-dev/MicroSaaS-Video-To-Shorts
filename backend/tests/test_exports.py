"""Tests for the Export & Publish endpoints (/clips/{id}/export, /status, /download).

`render_clip` is monkeypatched at the app.routers.exports import site so
tests exercise the endpoint contract (status transitions, polling,
download gating) without depending on a real ffmpeg binary.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus


def _make_clip(db_session: Session, user: User, **overrides) -> Clip:
    project = VideoProject(
        user_id=user.id,
        title="Export project",
        source_type=SourceType.upload,
        status=VideoProjectStatus.ready,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    defaults = dict(
        video_project_id=project.id,
        user_id=user.id,
        title="Clip",
        start_time=0.0,
        end_time=10.0,
        order_index=0,
        status=ClipStatus.draft,
    )
    defaults.update(overrides)
    clip = Clip(**defaults)
    db_session.add(clip)
    db_session.commit()
    db_session.refresh(clip)
    return clip


def _fake_render_success(clip_id: int) -> None:
    """Stand-in for video_render.render_clip that marks the clip ready
    without touching ffmpeg, mirroring the real function's contract of
    opening its own session and always leaving a terminal status."""

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        fresh = session.query(Clip).filter(Clip.id == clip_id).first()
        assert fresh is not None
        fresh.video_file_path = f"/tmp/exports/{clip_id}.mp4"
        fresh.status = ClipStatus.ready
        session.commit()
    finally:
        session.close()


def _fake_render_failure(clip_id: int) -> None:
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        fresh = session.query(Clip).filter(Clip.id == clip_id).first()
        assert fresh is not None
        fresh.status = ClipStatus.failed
        session.commit()
    finally:
        session.close()


class TestExportTrigger:
    def test_export_sets_status_rendering_then_settles_ready(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)

        with patch("app.routers.exports.render_clip", new=_fake_render_success):
            response = client.post(f"/api/v1/clips/{clip.id}/export", headers=auth_headers)

        assert response.status_code == 200
        # BackgroundTasks run synchronously under TestClient, so the fake
        # render already completed by the time we get the response here --
        # but the response body reflects the state set inline in the route
        # handler (status=rendering) before the DB was updated again.
        body = response.json()
        assert body["clip_id"] == clip.id
        assert body["status"] in {"rendering", "ready"}

        status_resp = client.get(
            f"/api/v1/clips/{clip.id}/export/status", headers=auth_headers
        )
        assert status_resp.json()["status"] == "ready"
        assert status_resp.json()["video_file_path"]

    def test_export_failure_settles_failed(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)

        with patch("app.routers.exports.render_clip", new=_fake_render_failure):
            client.post(f"/api/v1/clips/{clip.id}/export", headers=auth_headers)

        status_resp = client.get(
            f"/api/v1/clips/{clip.id}/export/status", headers=auth_headers
        )
        assert status_resp.json()["status"] == "failed"

    def test_export_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)
        response = client.post(f"/api/v1/clips/{clip.id}/export", headers=auth_headers)
        assert response.status_code == 404

    def test_export_nonexistent_clip_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post("/api/v1/clips/999999/export", headers=auth_headers)
        assert response.status_code == 404


class TestExportStatus:
    def test_status_reflects_current_state(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user, status=ClipStatus.draft)
        response = client.get(
            f"/api/v1/clips/{clip.id}/export/status", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "draft"

    def test_status_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)
        response = client.get(
            f"/api/v1/clips/{clip.id}/export/status", headers=auth_headers
        )
        assert response.status_code == 404


class TestDownload:
    def test_download_not_ready_422(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user, status=ClipStatus.draft)
        response = client.get(f"/api/v1/clips/{clip.id}/download", headers=auth_headers)
        assert response.status_code == 422

    def test_download_ready_but_file_missing_404(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(
            db_session,
            test_user,
            status=ClipStatus.ready,
            video_file_path="/nonexistent/path/clip.mp4",
        )
        response = client.get(f"/api/v1/clips/{clip.id}/download", headers=auth_headers)
        assert response.status_code == 404

    def test_download_ready_and_file_present_succeeds(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user,
        tmp_path: Path,
    ) -> None:
        video_file = tmp_path / "rendered.mp4"
        video_file.write_bytes(b"fake mp4 bytes")

        clip = _make_clip(
            db_session,
            test_user,
            status=ClipStatus.ready,
            video_file_path=str(video_file),
        )
        response = client.get(f"/api/v1/clips/{clip.id}/download", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert response.content == b"fake mp4 bytes"

    def test_download_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user, status=ClipStatus.ready)
        response = client.get(f"/api/v1/clips/{clip.id}/download", headers=auth_headers)
        assert response.status_code == 404


class TestPreview:
    """/clips/{id}/preview: inline streaming for <video> elements, which
    can't send an Authorization header -- auth is via a `?token=` query
    param instead (see get_current_user_for_media)."""

    def test_preview_draft_streams_source_video(
        self, client: TestClient, test_user: User, db_session: Session, tmp_path: Path
    ) -> None:
        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / "source.mp4"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_bytes(b"source video bytes")

        project = VideoProject(
            user_id=test_user.id,
            title="Preview project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/source.mp4",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Draft clip",
            start_time=5.0,
            end_time=45.0,
            order_index=0,
            status=ClipStatus.draft,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        token = create_access_token({"sub": str(test_user.id)})
        response = client.get(f"/api/v1/clips/{clip.id}/preview?token={token}")
        assert response.status_code == 200
        assert response.content == b"source video bytes"

    def test_preview_ready_streams_rendered_file_not_source(
        self, client: TestClient, test_user: User, db_session: Session, tmp_path: Path
    ) -> None:
        rendered_file = tmp_path / "rendered.mp4"
        rendered_file.write_bytes(b"rendered clip bytes")

        clip = _make_clip(
            db_session,
            test_user,
            status=ClipStatus.ready,
            video_file_path=str(rendered_file),
        )

        token = create_access_token({"sub": str(test_user.id)})
        response = client.get(f"/api/v1/clips/{clip.id}/preview?token={token}")
        assert response.status_code == 200
        assert response.content == b"rendered clip bytes"

    def test_preview_missing_token_401(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        clip = _make_clip(db_session, test_user)
        response = client.get(f"/api/v1/clips/{clip.id}/preview")
        assert response.status_code == 401

    def test_preview_other_users_clip_404(
        self,
        client: TestClient,
        test_user: User,
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)
        token = create_access_token({"sub": str(test_user.id)})
        response = client.get(f"/api/v1/clips/{clip.id}/preview?token={token}")
        assert response.status_code == 404

    def test_preview_no_source_file_404(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        clip = _make_clip(db_session, test_user, status=ClipStatus.draft)
        token = create_access_token({"sub": str(test_user.id)})
        response = client.get(f"/api/v1/clips/{clip.id}/preview?token={token}")
        assert response.status_code == 404
