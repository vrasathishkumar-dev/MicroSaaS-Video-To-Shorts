"""Tests for GET /api/v1/dashboard/stats."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus


class TestDashboardStats:
    def test_stats_with_no_data(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_videos"] == 0
        assert body["videos_by_status"] == {}
        assert body["total_clips"] == 0
        assert body["clips_ready"] == 0
        assert body["avg_processing_time_seconds"] is None

    def test_stats_aggregate_counts(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user: User
    ) -> None:
        ready_project = VideoProject(
            user_id=test_user.id,
            title="Ready",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        failed_project = VideoProject(
            user_id=test_user.id,
            title="Failed",
            source_type=SourceType.upload,
            status=VideoProjectStatus.failed,
            error_message="boom",
        )
        db_session.add_all([ready_project, failed_project])
        db_session.commit()
        db_session.refresh(ready_project)

        clip_ready = Clip(
            video_project_id=ready_project.id,
            user_id=test_user.id,
            title="Clip A",
            start_time=0.0,
            end_time=5.0,
            order_index=0,
            status=ClipStatus.ready,
        )
        clip_draft = Clip(
            video_project_id=ready_project.id,
            user_id=test_user.id,
            title="Clip B",
            start_time=5.0,
            end_time=10.0,
            order_index=1,
            status=ClipStatus.draft,
        )
        db_session.add_all([clip_ready, clip_draft])
        db_session.commit()

        response = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_videos"] == 2
        assert body["videos_by_status"]["ready"] == 1
        assert body["videos_by_status"]["failed"] == 1
        assert body["total_clips"] == 2
        assert body["clips_ready"] == 1

    def test_stats_only_scoped_to_current_user(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        other_project = VideoProject(
            user_id=other_user.id,
            title="Someone else's",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(other_project)
        db_session.commit()

        response = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total_videos"] == 0

    def test_stats_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/dashboard/stats")
        assert response.status_code == 401
