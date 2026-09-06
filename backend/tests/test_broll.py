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
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus
from app.services.broll_sourcing import (
    _extract_keywords_with_timing,
    _rank_score,
    _relevance,
    extract_keywords,
    extract_search_phrase,
    search_pexels,
    search_pixabay,
)


def _result(source: str, asset_id: str, **overrides: object) -> dict:
    """A fully-populated normalized search result, as the service now emits."""

    result = {
        "source": source,
        "source_asset_id": asset_id,
        "asset_url": f"https://{source}.example/{asset_id}.mp4",
        "preview_url": f"https://{source}.example/{asset_id}-tiny.mp4",
        "thumbnail_url": f"https://{source}.example/{asset_id}.jpg",
        "provider_url": f"https://{source}.example/video/{asset_id}",
        "author": "A Photographer",
        "description": "a mountain range at sunrise",
        "width": 1080,
        "height": 1920,
        "duration": 12.0,
        "keyword": "mountains",
    }
    result.update(overrides)
    return result


PEXELS_RESULTS = [_result("pexels", "111")]
PIXABAY_RESULTS = [_result("pixabay", "222")]


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

        # One distinct stock clip per keyword: auto-source never repeats an
        # asset within a single short, so a shared pool of three is what it
        # takes to fill all three keyword windows.
        pool = [_result("pexels", "111"), _result("pexels", "112"), _result("pexels", "113")]
        with patch(
            "app.services.broll_sourcing._search_all_providers",
            new=AsyncMock(return_value=pool),
        ):
            response = client.post(
                f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers
            )

        assert response.status_code == 200
        created = response.json()
        # caption_text "mountains hiking adventure" yields 3 keywords, each
        # of which resolves to a distinct (mocked) result.
        assert len(created) == 3
        assert all(item["clip_id"] == clip.id for item in created)
        assert all(item["source"] == "pexels" for item in created)
        assert len({item["source_asset_id"] for item in created}) == 3

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

    def test_auto_source_replaces_previous_batch_instead_of_duplicating(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """Regression test: clicking "Auto-insert B-roll" a second time used
        to insert another full batch on top of the first, since the
        endpoint had no way to tell its own previous rows apart from
        anything else attached to the clip."""

        clip = _make_clip(db_session, test_user)
        pool = [_result("pexels", "111"), _result("pexels", "112"), _result("pexels", "113")]

        with patch(
            "app.services.broll_sourcing._search_all_providers",
            new=AsyncMock(return_value=pool),
        ):
            first = client.post(f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers)
            second = client.post(f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert len(second.json()) == 3

        db_assets = db_session.query(BrollAsset).filter(BrollAsset.clip_id == clip.id).all()
        assert len(db_assets) == 3

    def test_auto_source_does_not_remove_manually_inserted_broll(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)
        manual_payload = {
            "source": "pexels",
            "source_asset_id": "999",
            "asset_url": "https://pexels.example/999.mp4",
            "keyword": "forest",
            "position_start": 0.0,
            "position_end": 2.0,
        }
        manual = client.post(
            f"/api/v1/clips/{clip.id}/broll", json=manual_payload, headers=auth_headers
        )
        assert manual.status_code == 200
        manual_id = manual.json()["id"]

        pool = [_result("pexels", "111"), _result("pexels", "112"), _result("pexels", "113")]
        with patch(
            "app.services.broll_sourcing._search_all_providers",
            new=AsyncMock(return_value=pool),
        ):
            client.post(f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers)
            client.post(f"/api/v1/clips/{clip.id}/broll/auto", headers=auth_headers)

        db_assets = db_session.query(BrollAsset).filter(BrollAsset.clip_id == clip.id).all()
        assert any(asset.id == manual_id for asset in db_assets)
        # 3 auto-generated (replaced, not duplicated) + the 1 manual insert.
        assert len(db_assets) == 4

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

    def test_manual_insert_rejects_non_positive_window(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        clip = _make_clip(db_session, test_user)
        payload = {
            "source": "pexels",
            "source_asset_id": "999",
            "asset_url": "https://pexels.example/999.mp4",
            "keyword": "forest",
            "position_start": 4.0,
            "position_end": 4.0,
        }
        response = client.post(
            f"/api/v1/clips/{clip.id}/broll", json=payload, headers=auth_headers
        )
        assert response.status_code == 422

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
            {
                "videos": [
                    {
                        "id": 55,
                        "url": "https://www.pexels.com/video/dogs-55/",
                        "image": "https://cdn.example/x.jpg",
                        "duration": 12,
                        "user": {"name": "A Photographer"},
                        "video_files": [
                            {"link": "https://cdn.example/x-hd.mp4", "width": 1080, "height": 1920},
                            {"link": "https://cdn.example/x-sd.mp4", "width": 640, "height": 1138},
                        ],
                    }
                ]
            }
        )

        async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        results = await search_pexels("dogs", per_page=1)
        assert results == [
            {
                "source": "pexels",
                "source_asset_id": "55",
                # Largest rendition within the export canvas renders...
                "asset_url": "https://cdn.example/x-hd.mp4",
                # ...while the small one backs the browser hover preview.
                "preview_url": "https://cdn.example/x-sd.mp4",
                "thumbnail_url": "https://cdn.example/x.jpg",
                "provider_url": "https://www.pexels.com/video/dogs-55/",
                "author": "A Photographer",
                # Pexels leaves `tags` empty and puts the real description
                # in the page URL, so the slug is what relevance ranks on.
                "description": "dogs",
                "width": 1080,
                "height": 1920,
                "duration": 12.0,
                "keyword": "dogs",
            }
        ]

    @pytest.mark.asyncio
    async def test_skips_videos_with_no_downloadable_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A Pexels entry whose renditions are unusable must be dropped, not
        backfilled with `video["url"]` -- that field is the Pexels *web page*,
        so storing it as asset_url hands ffmpeg an HTML document at render
        time and the B-roll silently never appears in the export."""

        fake_response = _FakeResponse(
            {
                "videos": [
                    {
                        "id": 55,
                        "url": "https://www.pexels.com/video/dogs-55/",
                        "video_files": [],
                    }
                ]
            }
        )

        async def fake_get(self, url, **kwargs):  # noqa: ANN001, ANN002, ANN003
            return fake_response

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        assert await search_pexels("dogs") == []

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
            {
                "hits": [
                    {
                        "id": 77,
                        "pageURL": "https://pixabay.com/videos/id-77/",
                        "tags": "cats, kitten, pet",
                        "duration": 20,
                        "user": "A Videographer",
                        "videos": {
                            # Pixabay returns an entry for every size but
                            # leaves `url` empty for ones it hasn't
                            # rendered; "large" here must be skipped rather
                            # than stored as an empty asset_url.
                            "large": {"url": "", "width": 0, "height": 0},
                            "medium": {
                                "url": "https://cdn.example/y.mp4",
                                "thumbnail": "https://cdn.example/y.jpg",
                                "width": 1080,
                                "height": 1920,
                            },
                            "tiny": {
                                "url": "https://cdn.example/y-tiny.mp4",
                                "width": 360,
                                "height": 640,
                            },
                        },
                    }
                ]
            }
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
                "preview_url": "https://cdn.example/y-tiny.mp4",
                "thumbnail_url": "https://cdn.example/y.jpg",
                "provider_url": "https://pixabay.com/videos/id-77/",
                "author": "A Videographer",
                "description": "cats, kitten, pet",
                "width": 1080,
                "height": 1920,
                "duration": 20.0,
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


class TestSearchPhrases:
    """Stock libraries index scenes, not vocabulary, so the query sent to a
    provider has to name something filmable."""

    def test_builds_a_noun_phrase_from_a_spoken_sentence(self) -> None:
        assert (
            extract_search_phrase("that the espresso machine really matters a lot")
            == "espresso machine"
        )
        assert (
            extract_search_phrase("we went to the mountain trail last weekend")
            == "mountain trail"
        )

    def test_adverbs_never_become_a_query(self) -> None:
        """Regression: ranking broke ties by word length, so long adverbs
        beat the concrete nouns beside them and the query became
        "absolutely incredible" -- which matches no stock footage."""

        phrase = extract_search_phrase(
            "the sunrise over the canyon was absolutely incredible"
        )
        assert "absolutely" not in phrase
        assert "incredible" not in phrase
        assert phrase == "sunrise canyon"

    def test_a_real_ly_noun_survives(self) -> None:
        assert "family" in extract_search_phrase("the whole family gathered outside")

    def test_prefers_the_noun_pair_over_the_verb_pair(self) -> None:
        """Both "surgeon walked" and "operating room" are adjacent pairs
        here; only the second names something to point a camera at."""

        assert (
            extract_search_phrase("the surgeon walked into the operating room")
            == "operating room"
        )

    def test_falls_back_to_nothing_when_there_is_nothing_visual(self) -> None:
        assert extract_search_phrase("well I mean you know basically") == ""


class TestExtractKeywordsWithTiming:
    """Regression coverage for full-clip B-roll coverage: a hard 3-keyword
    cap and per-phrase dedup used to leave most of a clip -- everything
    after the first ~8 seconds -- with no B-roll window at all."""

    @staticmethod
    def _clip_with_segments(
        db_session: Session, user: User, segments: list[tuple[float, float, str]]
    ) -> Clip:
        project = VideoProject(
            user_id=user.id,
            title="Timing project",
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
            end_time=max(end for _, end, _ in segments),
            order_index=0,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        for start, end, text in segments:
            db_session.add(
                TranscriptSegment(
                    video_project_id=project.id, start_time=start, end_time=end, text=text
                )
            )
        db_session.commit()
        db_session.refresh(clip)
        return clip

    def test_windows_cover_the_full_clip_back_to_back(
        self, db_session: Session, test_user: User
    ) -> None:
        clip = self._clip_with_segments(
            db_session,
            test_user,
            [
                (1.0, 3.0, "the mountain trail was steep"),
                (5.0, 7.0, "we reached the ocean shore"),
                (7.0, 9.5, "the campfire glowed warm"),
            ],
        )

        timings = _extract_keywords_with_timing(clip)

        assert timings[0][1] == 0.0, "first window must start at clip time 0"
        assert timings[-1][2] == clip.end_time, "last window must reach clip end"
        for (_, _, end), (_, next_start, _) in zip(timings, timings[1:], strict=False):
            assert end == next_start, "no gap is allowed between windows"

    def test_more_than_three_spoken_segments_all_get_a_window(
        self, db_session: Session, test_user: User
    ) -> None:
        """Regression: a hard cap of 3 used to mean a clip with more than
        three spoken segments got B-roll only for its first few seconds."""

        segments = [
            (float(i * 2), float(i * 2 + 2), f"the sunrise over the canyon number {i}")
            for i in range(6)
        ]
        clip = self._clip_with_segments(db_session, test_user, segments)

        timings = _extract_keywords_with_timing(clip)

        assert len(timings) == 6

    def test_a_repeated_phrase_does_not_create_a_gap(
        self, db_session: Session, test_user: User
    ) -> None:
        """Regression: dedup used to skip a segment outright when its
        extracted phrase repeated an earlier one, leaving that stretch of
        the clip with no B-roll window at all."""

        clip = self._clip_with_segments(
            db_session,
            test_user,
            [
                (0.0, 2.0, "the mountain trail was steep"),
                (2.0, 4.0, "the mountain trail kept climbing"),
            ],
        )

        timings = _extract_keywords_with_timing(clip)

        assert len(timings) == 2
        assert timings[0][2] == timings[1][1] == 2.0


class TestRelevanceRanking:
    """Providers rank by their own popularity signals, not by fit."""

    def test_scores_overlap_with_the_clip_description(self) -> None:
        assert _relevance("espresso machine", "an espresso machine in a cafe") == 1.0
        assert _relevance("espresso machine", "a coffee cup on a table") == 0.0
        assert _relevance("espresso machine", "a machine in a workshop") == 0.5

    def test_missing_description_is_not_punished(self) -> None:
        """A provider that returns no description should fall back to the
        other signals, not be ranked below an irrelevant clip."""

        assert _relevance("espresso machine", "") == 0.0

    def test_the_relevant_clip_outranks_the_merely_vertical_one(self) -> None:
        relevant_landscape = _result(
            "pixabay", "1", description="an espresso machine pouring coffee",
            width=1920, height=1080, keyword="espresso machine",
        )
        irrelevant_portrait = _result(
            "pexels", "2", description="a dog running on a beach",
            width=1080, height=1920, keyword="espresso machine",
        )
        assert _rank_score(relevant_landscape) > _rank_score(irrelevant_portrait)

    def test_between_two_relevant_clips_the_vertical_one_wins(self) -> None:
        portrait = _result(
            "pexels", "1", description="an espresso machine",
            width=1080, height=1920, keyword="espresso machine",
        )
        landscape = _result(
            "pixabay", "2", description="an espresso machine",
            width=1920, height=1080, keyword="espresso machine",
        )
        assert _rank_score(portrait) > _rank_score(landscape)
