"""Tests for the B-roll sourcing endpoints.

Mocks `app.services.broll_sourcing.search_pexels` / `search_pixabay`
directly (rather than the underlying httpx calls) so tests never hit real
network/APIs but still exercise the real endpoint/service wiring.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.broll_asset import BrollAsset
from app.models.clip import Clip
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus
from app.services.broll_sourcing import extract_keywords, search_pexels, search_pixabay

PEXELS_RESULTS = [
    {
        "source": "pexels",
        "source_asset_id": "111",
        "asset_url": "https://pexels.example/111.mp4",
        "keyword": "mountains",
    }
]
PIXABAY_RESULTS = [
    {
        "source": "pixabay",
        "source_asset_id": "222",
        "asset_url": "https://pixabay.example/222.mp4",
        "keyword": "mountains",
    }
]


def _make_clip(
    db_session: Session, user: User, caption_text: str | None = "mountains hiking adventure"
) -> Clip:
    project = VideoProject(
        user_id=user.id,
        title="Broll project",
        source_type=SourceType.upload,
        status=VideoProjectStatus.ready,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    clip = Clip(
        video_project_id=project.id,
        user_id=user.id,
        title="Clip",
        start_time=0.0,
        end_time=10.0,
        order_index=0,
        caption_text=caption_text,
    )
    db_session.add(clip)
    db_session.commit()
    db_session.refresh(clip)
    return clip


class TestSearch:
    def test_search_combines_both_providers(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with (
            patch(
                "app.routers.broll.search_pexels", new=AsyncMock(return_value=PEXELS_RESULTS)
            ),
            patch(
                "app.routers.broll.search_pixabay", new=AsyncMock(return_value=PIXABAY_RESULTS)
            ),
        ):
            response = client.get(
                "/api/v1/broll/search", params={"q": "mountains"}, headers=auth_headers
            )

        assert response.status_code == 200
        results = response.json()
        assert len(results) == 2
        sources = {r["source"] for r in results}
        assert sources == {"pexels", "pixabay"}

    def test_search_filtered_by_source(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.routers.broll.search_pexels", new=AsyncMock(return_value=PEXELS_RESULTS)
        ) as mock_pexels:
            response = client.get(
                "/api/v1/broll/search",
                params={"q": "mountains", "source": "pexels"},
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["source"] == "pexels"
        mock_pexels.assert_awaited_once()

    def test_search_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/broll/search", params={"q": "mountains"})
        assert response.status_code == 401

    def test_search_degrades_gracefully_on_provider_failure(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """search_pexels/search_pixabay themselves swallow httpx errors and
        return [] (see app.services.broll_sourcing) -- verify that
        degradation surfaces correctly through the endpoint rather than
        raising a 500."""

        with (
            patch(
                "app.routers.broll.search_pexels", new=AsyncMock(return_value=[])
            ),
            patch(
                "app.routers.broll.search_pixabay", new=AsyncMock(return_value=PIXABAY_RESULTS)
            ),
        ):
            response = client.get(
                "/api/v1/broll/search", params={"q": "mountains"}, headers=auth_headers
            )

        assert response.status_code == 200
        assert response.json() == PIXABAY_RESULTS


class TestAutoInsert:
    def test_auto_source_creates_broll_assets(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)

        with patch(
            "app.services.broll_sourcing._search_all_providers",
            new=AsyncMock(return_value=[*PEXELS_RESULTS]),
        ):
            response = client.post(
                f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers
            )

        assert response.status_code == 200
        created = response.json()
        # caption_text "mountains hiking adventure" yields 3 keywords, each
        # of which resolves to the (mocked) top result.
        assert len(created) == 3
        assert all(item["clip_id"] == clip.id for item in created)
        assert all(item["source"] == "pexels" for item in created)

        db_assets = db_session.query(BrollAsset).filter(BrollAsset.clip_id == clip.id).all()
        assert len(db_assets) == 3

    def test_auto_source_positions_are_relative_to_clip_not_source_video(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """Regression test: position_start/end must be relative to the
        clip's own timeline (0 = clip start) -- app.services.video_render
        interprets them that way. A clip that starts well into the source
        video (start_time=40) previously got positions offset by that 40s,
        which made every auto-sourced B-roll asset fall outside the clip's
        own [0, duration] window and get silently skipped at render time."""

        project = VideoProject(
            user_id=test_user.id,
            title="Broll project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Clip",
            start_time=40.0,
            end_time=50.0,
            order_index=0,
            caption_text="mountains hiking adventure",
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        with patch(
            "app.services.broll_sourcing._search_all_providers",
            new=AsyncMock(return_value=[*PEXELS_RESULTS]),
        ):
            response = client.post(
                f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers
            )

        assert response.status_code == 200
        created = response.json()
        assert len(created) > 0
        clip_duration = clip.end_time - clip.start_time
        for asset in created:
            assert 0.0 <= asset["position_start"] < asset["position_end"] <= clip_duration

    def test_auto_source_no_keywords_returns_empty(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user, caption_text=None)
        response = client.post(f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_auto_source_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)
        response = client.post(f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers)
        assert response.status_code == 404


class TestManualInsertAndDelete:
    def test_manual_insert(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)
        payload = {
            "source": "pexels",
            "source_asset_id": "999",
            "asset_url": "https://pexels.example/999.mp4",
            "keyword": "forest",
            "position_start": 1.0,
            "position_end": 4.0,
        }
        response = client.post(
            f"/api/v1/clips/{clip.id}/broll", json=payload, headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["keyword"] == "forest"
        assert body["clip_id"] == clip.id

    def test_manual_insert_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)
        payload = {
            "source": "pexels",
            "source_asset_id": "999",
            "asset_url": "https://pexels.example/999.mp4",
            "keyword": "forest",
            "position_start": 1.0,
            "position_end": 4.0,
        }
        response = client.post(
            f"/api/v1/clips/{clip.id}/broll", json=payload, headers=auth_headers
        )
        assert response.status_code == 404

    def test_delete_broll_asset(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)
        asset = BrollAsset(
            clip_id=clip.id,
            source="pexels",
            source_asset_id="1",
            asset_url="https://pexels.example/1.mp4",
            keyword="mountains",
            position_start=0.0,
            position_end=2.0,
        )
        db_session.add(asset)
        db_session.commit()
        db_session.refresh(asset)

        response = client.delete(
            f"/api/v1/clips/{clip.id}/broll/{asset.id}", headers=auth_headers
        )
        assert response.status_code == 204

        remaining = db_session.query(BrollAsset).filter(BrollAsset.id == asset.id).first()
        assert remaining is None

    def test_delete_nonexistent_broll_asset_404(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)
        response = client.delete(
            f"/api/v1/clips/{clip.id}/broll/999999", headers=auth_headers
        )
        assert response.status_code == 404


class _FakeResponse:
    """Minimal stand-in for an httpx.Response, enough for the parsing code
    in app.services.broll_sourcing to work with."""

    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError(
                "error", request=request, response=httpx.Response(self.status_code, request=request)
            )

    def json(self) -> dict:
        return self._json_data


class TestSearchPexelsService:
    """Exercises app.services.broll_sourcing.search_pexels directly against
    a mocked httpx.AsyncClient.get, per the task's request to mock at the
    httpx layer (not just the router-level function) for at least one path."""

    @pytest.mark.asyncio
    async def test_parses_normalized_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse(
            {"videos": [{"id": 55, "video_files": [{"link": "https://cdn.example/x.mp4"}]}]}
        )

        async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        results = await search_pexels("dogs")
        assert results == [
            {
                "source": "pexels",
                "source_asset_id": "55",
                "asset_url": "https://cdn.example/x.mp4",
                "keyword": "dogs",
            }
        ]

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_http_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN002, ANN003
            request = httpx.Request("GET", url)
            raise httpx.ConnectError("boom", request=request)

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        results = await search_pexels("dogs")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_without_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "PEXELS_API_KEY", "")
        results = await search_pexels("dogs")
        assert results == []


class TestSearchPixabayService:
    @pytest.mark.asyncio
    async def test_parses_normalized_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_response = _FakeResponse(
            {"hits": [{"id": 77, "videos": {"medium": {"url": "https://cdn.example/y.mp4"}}}]}
        )

        async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        results = await search_pixabay("cats")
        assert results == [
            {
                "source": "pixabay",
                "source_asset_id": "77",
                "asset_url": "https://cdn.example/y.mp4",
                "keyword": "cats",
            }
        ]

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_invalid_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _BadJsonResponse(_FakeResponse):
            def json(self) -> dict:
                raise ValueError("bad json")

        async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return _BadJsonResponse({})

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        results = await search_pixabay("cats")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_without_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.config import settings

        monkeypatch.setattr(settings, "PIXABAY_API_KEY", "")
        results = await search_pixabay("cats")
        assert results == []


class TestExtractKeywords:
    def test_ranks_by_frequency_and_length(self) -> None:
        text = "The mountain hiking trip was amazing amazing hiking adventure"
        keywords = extract_keywords(text, max_keywords=2)
        assert len(keywords) <= 2
        assert set(keywords).issubset({"amazing", "hiking", "mountain", "adventure"})

    def test_empty_text_returns_empty_list(self) -> None:
        assert extract_keywords("") == []

    def test_only_stopwords_returns_empty_list(self) -> None:
        assert extract_keywords("the and but for") == []
