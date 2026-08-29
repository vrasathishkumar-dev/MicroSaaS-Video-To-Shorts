"""Tests for /api/v1/auth/* endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _register(client: TestClient, email: str = "new@example.com", password: str = "Password123!"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "New User"},
    )


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


class TestRegister:
    def test_register_success(self, client: TestClient) -> None:
        response = _register(client)
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "new@example.com"
        assert body["full_name"] == "New User"
        assert body["is_active"] is True
        assert "id" in body
        assert "hashed_password" not in body

    def test_register_duplicate_email_conflict(self, client: TestClient) -> None:
        first = _register(client, email="dupe@example.com")
        assert first.status_code == 201

        second = _register(client, email="dupe@example.com")
        assert second.status_code == 409
        assert second.json()["code"] == "CONFLICT"

    def test_register_password_too_short_is_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "short@example.com", "password": "short"},
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client: TestClient) -> None:
        _register(client, email="login@example.com", password="Password123!")
        response = _login(client, "login@example.com", "Password123!")
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient) -> None:
        _register(client, email="wrongpw@example.com", password="Password123!")
        response = _login(client, "wrongpw@example.com", "WrongPassword!")
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient) -> None:
        response = _login(client, "doesnotexist@example.com", "whatever123")
        assert response.status_code == 401

    def test_login_inactive_user(self, client: TestClient, db_session: Session) -> None:
        _register(client, email="inactive@example.com", password="Password123!")
        user = db_session.query(User).filter(User.email == "inactive@example.com").first()
        assert user is not None
        user.is_active = False
        db_session.commit()

        response = _login(client, "inactive@example.com", "Password123!")
        assert response.status_code == 401


class TestRefreshAndLogout:
    def test_refresh_rotates_tokens(self, client: TestClient) -> None:
        _register(client, email="refresh@example.com", password="Password123!")
        login_resp = _login(client, "refresh@example.com", "Password123!")
        original_refresh = login_resp.json()["refresh_token"]

        refresh_resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": original_refresh}
        )
        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

        # The old refresh token was revoked by rotation and can't be reused,
        # regardless of whether the newly-issued JWT string happens to
        # differ (two tokens minted for the same user in the same second
        # can be byte-identical, since exp has only second resolution).
        reuse_resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": original_refresh}
        )
        assert reuse_resp.status_code == 401

    def test_refresh_invalid_token(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
        )
        assert response.status_code == 401

    def test_logout_revokes_refresh_token(self, client: TestClient) -> None:
        _register(client, email="logout@example.com", password="Password123!")
        login_resp = _login(client, "logout@example.com", "Password123!")
        refresh_token = login_resp.json()["refresh_token"]

        logout_resp = client.post(
            "/api/v1/auth/logout", json={"refresh_token": refresh_token}
        )
        assert logout_resp.status_code == 204

        # The revoked token can no longer be used to refresh.
        refresh_resp = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_resp.status_code == 401

    def test_logout_unknown_token_is_noop(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/logout", json={"refresh_token": "unknown-token"}
        )
        assert response.status_code == 204


class TestMe:
    def test_get_me_unauthenticated_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_get_me_authenticated(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "testuser@example.com"

    def test_get_me_invalid_token_401(self, client: TestClient) -> None:
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer garbage-token"}
        )
        assert response.status_code == 401

    def test_update_me(self, client: TestClient, auth_headers: dict[str, str]) -> None:
        response = client.put(
            "/api/v1/auth/me",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Updated Name"

    def test_update_me_unauthenticated_401(self, client: TestClient) -> None:
        response = client.put("/api/v1/auth/me", json={"full_name": "Nope"})
        assert response.status_code == 401


class TestRateLimit:
    def test_rate_limit_triggers_after_n_requests(self, client: TestClient) -> None:
        """The auth rate limiter allows 5 requests/60s per client; the 6th 429s."""

        responses = [
            _register(client, email=f"rl{i}@example.com") for i in range(6)
        ]
        statuses = [r.status_code for r in responses]
        assert statuses[:5] == [201, 409, 409, 409, 409] or 429 not in statuses[:5]
        assert 429 in statuses, f"expected a 429 among {statuses}"

    def test_normal_usage_not_rate_limited(self, client: TestClient) -> None:
        """A single register + login pair should never be rate-limited."""

        register_resp = _register(client, email="normal@example.com")
        assert register_resp.status_code == 201
        login_resp = _login(client, "normal@example.com", "Password123!")
        assert login_resp.status_code == 200
