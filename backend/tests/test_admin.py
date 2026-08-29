"""Tests for /api/v1/admin/* endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus


class TestNonAdminForbidden:
    def test_list_users_403_for_non_admin(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/api/v1/admin/users", headers=auth_headers)
        assert response.status_code == 403

    def test_update_user_403_for_non_admin(
        self, client: TestClient, auth_headers: dict[str, str], test_user: User
    ) -> None:
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_stats_403_for_non_admin(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/api/v1/admin/stats", headers=auth_headers)
        assert response.status_code == 403

    def test_all_admin_routes_401_when_unauthenticated(self, client: TestClient) -> None:
        assert client.get("/api/v1/admin/users").status_code == 401
        assert client.get("/api/v1/admin/stats").status_code == 401
        assert client.put("/api/v1/admin/users/1", json={"is_active": False}).status_code == 401


class TestAdminListAndSearchUsers:
    def test_admin_can_list_users(
        self, client: TestClient, admin_headers: dict[str, str], test_user: User
    ) -> None:
        response = client.get("/api/v1/admin/users", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        # test_user + the admin itself
        assert body["total"] == 2
        emails = {u["email"] for u in body["items"]}
        assert "testuser@example.com" in emails
        assert "admin@example.com" in emails

    def test_admin_can_search_users_by_email_substring(
        self, client: TestClient, admin_headers: dict[str, str], test_user: User
    ) -> None:
        response = client.get(
            "/api/v1/admin/users", params={"q": "testuser"}, headers=admin_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "testuser@example.com"

    def test_admin_search_no_match(
        self, client: TestClient, admin_headers: dict[str, str], test_user: User
    ) -> None:
        response = client.get(
            "/api/v1/admin/users", params={"q": "nobody-matches-this"}, headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_admin_list_users_pagination(
        self, client: TestClient, admin_headers: dict[str, str], test_user: User, other_user: User
    ) -> None:
        response = client.get(
            "/api/v1/admin/users",
            params={"page": 1, "page_size": 2},
            headers=admin_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3  # admin + test_user + other_user
        assert len(body["items"]) == 2


class TestAdminActivateDeactivate:
    def test_admin_can_deactivate_user(
        self, client: TestClient, admin_headers: dict[str, str], test_user: User
    ) -> None:
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_admin_can_reactivate_user(
        self, client: TestClient, admin_headers: dict[str, str], test_user: User
    ) -> None:
        client.put(
            f"/api/v1/admin/users/{test_user.id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}",
            json={"is_active": True},
            headers=admin_headers,
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_admin_update_nonexistent_user_404(
        self, client: TestClient, admin_headers: dict[str, str]
    ) -> None:
        response = client.put(
            "/api/v1/admin/users/999999",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_admin_cannot_deactivate_self(
        self, client: TestClient, admin_headers: dict[str, str], admin_user: User
    ) -> None:
        response = client.put(
            f"/api/v1/admin/users/{admin_user.id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert response.status_code == 422
        assert "cannot deactivate" in response.json()["message"].lower()


class TestAdminStats:
    def test_admin_stats(
        self,
        client: TestClient,
        admin_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        project = VideoProject(
            user_id=test_user.id,
            title="Some video",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()

        response = client.get("/api/v1/admin/stats", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_users"] >= 2  # admin + test_user
        assert body["total_videos"] >= 1
        assert "total_clips" in body
        assert "active_users_last_30_days" in body
