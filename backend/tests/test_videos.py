"""Tests for /api/v1/videos/* endpoints.

Note on background processing: POST /videos and POST /videos/{id}/process
return immediately with the project's state *as of creation/reset* (always
status="pending") -- the response body is serialized before the scheduled
`process_video_project` BackgroundTask runs. Under TestClient, that
background task does complete synchronously before `client.post(...)`
returns control to the test, so a follow-up GET reliably observes the
final status.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus

FAKE_SEGMENTS = [
    {"start_time": 0.0, "end_time": 5.0, "text": "This is the first segment."},
    {"start_time": 5.0, "end_time": 12.0, "text": "This is the second segment."},
]


def _create_upload_project(
    client: TestClient, headers: dict[str, str], title: str = "My Video"
):
    files = {"file": ("clip.mp4", b"fake video bytes", "video/mp4")}
    data = {"title": title, "source_type": "upload"}
    return client.post("/api/v1/videos", data=data, files=files, headers=headers)


class TestCreateUpload:
    def test_create_via_upload_success(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            response = _create_upload_project(client, auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "My Video"
        assert body["source_type"] == "upload"
        assert body["status"] == "pending"  # not yet processed at response time

        # The background pipeline ran synchronously (under TestClient) by
        # the time client.post() returned, so a follow-up GET reflects it.
        get_resp = client.get(f"/api/v1/videos/{body['id']}", headers=auth_headers)
        assert get_resp.json()["status"] == "ready"
        assert get_resp.json()["broll_placement"] == "bottom"

    def test_create_via_upload_custom_broll_placement(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            files = {"file": ("clip.mp4", b"fake video bytes", "video/mp4")}
            data = {
                "title": "Split B-Roll Project",
                "source_type": "upload",
                "broll_placement": "split",
            }
            response = client.post("/api/v1/videos", data=data, files=files, headers=auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["broll_placement"] == "split"

        get_resp = client.get(f"/api/v1/videos/{body['id']}", headers=auth_headers)
        assert get_resp.json()["broll_placement"] == "split"

    def test_create_via_upload_missing_file_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        data = {"title": "No File", "source_type": "upload"}
        response = client.post("/api/v1/videos", data=data, headers=auth_headers)
        assert response.status_code == 422

    def test_create_via_upload_unauthenticated_401(self, client: TestClient) -> None:
        files = {"file": ("clip.mp4", b"fake video bytes", "video/mp4")}
        data = {"title": "No Auth", "source_type": "upload"}
        response = client.post("/api/v1/videos", data=data, files=files)
        assert response.status_code == 401


class TestCreateUrl:
    def test_create_via_url_success(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with (
            patch(
                "app.routers.videos.storage.download_from_url",
                new=AsyncMock(return_value="videos/downloaded.mp4"),
            ) as mock_download,
            patch(
                "app.routers.videos.transcribe_video",
                new=AsyncMock(return_value=FAKE_SEGMENTS),
            ),
        ):
            response = client.post(
                "/api/v1/videos",
                data={
                    "title": "URL Video",
                    "source_type": "url",
                    "source_url": "https://example.com/video.mp4",
                },
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["source_type"] == "url"
        assert body["source_url"] == "https://example.com/video.mp4"
        mock_download.assert_awaited_once()

        get_resp = client.get(f"/api/v1/videos/{body['id']}", headers=auth_headers)
        assert get_resp.json()["status"] == "ready"
        assert get_resp.json()["source_file_path"] == "videos/downloaded.mp4"

    def test_create_via_url_missing_source_url_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/videos",
            data={"title": "No URL", "source_type": "url"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_via_url_download_failure_marks_failed(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session
    ) -> None:
        from app.exceptions import ValidationAppError

        with patch(
            "app.routers.videos.storage.download_from_url",
            new=AsyncMock(side_effect=ValidationAppError("Could not download")),
        ):
            response = client.post(
                "/api/v1/videos",
                data={
                    "title": "Broken URL",
                    "source_type": "url",
                    "source_url": "https://example.com/broken.mp4",
                },
                headers=auth_headers,
            )

        assert response.status_code == 201  # creation itself succeeds
        project_id = response.json()["id"]

        get_resp = client.get(f"/api/v1/videos/{project_id}", headers=auth_headers)
        assert get_resp.json()["status"] == "failed"
        assert get_resp.json()["error_message"]


class TestSubmissionOptions:
    """The submit form's AI options. They are settings for the shorts, not
    UI decoration: what gets picked here has to survive to the clips."""

    def test_options_are_saved_with_the_project(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with (
            patch(
                "app.routers.videos.storage.download_from_url",
                new=AsyncMock(return_value="videos/downloaded.mp4"),
            ),
            patch(
                "app.routers.videos.transcribe_video",
                new=AsyncMock(return_value=FAKE_SEGMENTS),
            ),
        ):
            response = client.post(
                "/api/v1/videos",
                data={
                    "title": "Configured Video",
                    "source_type": "url",
                    "source_url": "https://example.com/video.mp4",
                    "target_clip_length": "fast",
                    "framing_mode": "dynamic_blur",
                    "caption_style": "karaoke",
                    "auto_broll": "false",
                },
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["target_clip_length"] == "fast"
        assert body["framing_mode"] == "dynamic_blur"
        assert body["caption_style"] == "karaoke"
        assert body["auto_broll"] is False

    def test_a_bare_submission_still_works(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        """The options panel is collapsed by default, so a submission that
        sends none of them has to land on sensible defaults."""

        with (
            patch(
                "app.routers.videos.storage.download_from_url",
                new=AsyncMock(return_value="videos/downloaded.mp4"),
            ),
            patch(
                "app.routers.videos.transcribe_video",
                new=AsyncMock(return_value=FAKE_SEGMENTS),
            ),
        ):
            response = client.post(
                "/api/v1/videos",
                data={
                    "title": "Plain Video",
                    "source_type": "url",
                    "source_url": "https://example.com/video.mp4",
                },
                headers=auth_headers,
            )

        assert response.status_code == 201
        body = response.json()
        assert body["target_clip_length"] == "auto"
        assert body["framing_mode"] == "speaker_focus"
        assert body["caption_style"] == "hormozi"
        assert body["auto_broll"] is True

    def test_an_unknown_option_is_rejected(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/videos",
            data={
                "title": "Bad Video",
                "source_type": "url",
                "source_url": "https://example.com/video.mp4",
                "target_clip_length": "epic",
            },
            headers=auth_headers,
        )

        assert response.status_code == 422


class TestListAndGet:
    def test_list_video_projects_pagination(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            for i in range(3):
                _create_upload_project(client, auth_headers, title=f"Video {i}")

        response = client.get(
            "/api/v1/videos", params={"page": 1, "page_size": 2}, headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 2
        assert len(body["items"]) == 2

        page2 = client.get(
            "/api/v1/videos", params={"page": 2, "page_size": 2}, headers=auth_headers
        )
        assert len(page2.json()["items"]) == 1

    def test_list_only_returns_own_projects(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        other = VideoProject(
            user_id=other_user.id,
            title="Someone else's video",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(other)
        db_session.commit()

        response = client.get("/api/v1/videos", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_get_video_project_by_id(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            create_resp = _create_upload_project(client, auth_headers)
        project_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/videos/{project_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == project_id

    def test_get_other_users_project_is_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        other = VideoProject(
            user_id=other_user.id,
            title="Not yours",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        response = client.get(f"/api/v1/videos/{other.id}", headers=auth_headers)
        assert response.status_code == 404

    def test_get_nonexistent_project_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/api/v1/videos/999999", headers=auth_headers)
        assert response.status_code == 404


class TestDelete:
    def test_delete_video_project(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session
    ) -> None:
        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            create_resp = _create_upload_project(client, auth_headers)
        project_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/v1/videos/{project_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        get_resp = client.get(f"/api/v1/videos/{project_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    def test_delete_other_users_project_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        other = VideoProject(
            user_id=other_user.id,
            title="Not yours",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        response = client.delete(f"/api/v1/videos/{other.id}", headers=auth_headers)
        assert response.status_code == 404


class TestTranscript:
    def test_transcript_ordered_by_start_time(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        project = VideoProject(
            user_id=test_user.id,
            title="Transcript video",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Insert out of order to verify the endpoint sorts by start_time.
        db_session.add_all(
            [
                TranscriptSegment(
                    video_project_id=project.id, start_time=10.0, end_time=15.0, text="Third"
                ),
                TranscriptSegment(
                    video_project_id=project.id, start_time=0.0, end_time=4.0, text="First"
                ),
                TranscriptSegment(
                    video_project_id=project.id, start_time=4.0, end_time=10.0, text="Second"
                ),
            ]
        )
        db_session.commit()

        response = client.get(
            f"/api/v1/videos/{project.id}/transcript", headers=auth_headers
        )
        assert response.status_code == 200
        texts = [seg["text"] for seg in response.json()]
        assert texts == ["First", "Second", "Third"]

    def test_transcript_for_other_users_project_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        other = VideoProject(
            user_id=other_user.id,
            title="Not yours",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        response = client.get(
            f"/api/v1/videos/{other.id}/transcript", headers=auth_headers
        )
        assert response.status_code == 404


class TestReprocess:
    def test_reprocess_resets_status_and_reruns_pipeline(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            create_resp = _create_upload_project(client, auth_headers)
        project_id = create_resp.json()["id"]

        with patch(
            "app.routers.videos.transcribe_video",
            new=AsyncMock(return_value=FAKE_SEGMENTS),
        ):
            response = client.post(
                f"/api/v1/videos/{project_id}/process", headers=auth_headers
            )

        assert response.status_code == 200
        assert response.json()["status"] == "pending"

        get_resp = client.get(f"/api/v1/videos/{project_id}", headers=auth_headers)
        assert get_resp.json()["status"] == "ready"

    def test_reprocess_other_users_project_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        other = VideoProject(
            user_id=other_user.id,
            title="Not yours",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(other)
        db_session.commit()
        db_session.refresh(other)

        response = client.post(
            f"/api/v1/videos/{other.id}/process", headers=auth_headers
        )
        assert response.status_code == 404


class TestViralVerificationPipeline:
    def test_produce_clips_skips_when_no_viral_content(
        self, db_session: Session, test_user: User
    ) -> None:
        """If all clips score below virality threshold (50.0), no videos are rendered."""
        from app.models.clip import Clip, ClipStatus
        from app.routers.videos import _produce_clips_for_project

        project = VideoProject(
            user_id=test_user.id,
            title="Non-viral Project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/dummy.mp4",
        )
        db_session.add(project)
        db_session.commit()

        # Mock create_clips_from_highlights returning sub-50 clips
        sub_clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Boring clip",
            start_time=0.0,
            end_time=10.0,
            order_index=0,
            status=ClipStatus.draft,
            virality_score=35.0,
        )
        db_session.add(sub_clip)
        db_session.commit()

        import asyncio
        with (
            patch(
                "app.services.clip_service.create_clips_from_highlights",
                return_value=[sub_clip],
            ),
            patch("app.routers.videos.render_clip") as mock_render,
        ):
            asyncio.run(_produce_clips_for_project(db_session, project))

        assert not mock_render.called
        db_session.refresh(sub_clip)
        assert sub_clip.status == ClipStatus.draft

    def test_produce_clips_renders_only_viral_clips(
        self, db_session: Session, test_user: User
    ) -> None:
        """Only clips with virality_score >= 50.0 are rendered into videos."""
        from app.models.clip import Clip, ClipStatus
        from app.routers.videos import _produce_clips_for_project

        project = VideoProject(
            user_id=test_user.id,
            title="Viral Project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/dummy.mp4",
        )
        db_session.add(project)
        db_session.commit()

        weak_clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Weak clip",
            start_time=0.0,
            end_time=10.0,
            order_index=0,
            status=ClipStatus.draft,
            virality_score=40.0,
        )
        viral_clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Viral clip",
            start_time=10.0,
            end_time=25.0,
            order_index=1,
            status=ClipStatus.draft,
            virality_score=85.0,
        )
        db_session.add_all([weak_clip, viral_clip])
        db_session.commit()

        import asyncio
        with (
            patch(
                "app.services.clip_service.create_clips_from_highlights",
                return_value=[weak_clip, viral_clip],
            ),
            patch("app.routers.videos.storage.get_file_path") as mock_fp,
            patch("app.routers.videos.render_clip") as mock_render,
        ):
            mock_fp.return_value.is_file.return_value = True
            asyncio.run(_produce_clips_for_project(db_session, project))

        # Only the viral clip was sent to render_clip
        assert mock_render.called
        assert mock_render.call_count == 1
        assert mock_render.call_args[0][0] == viral_clip.id

        db_session.refresh(weak_clip)
        db_session.refresh(viral_clip)
        assert weak_clip.status == ClipStatus.draft
        assert viral_clip.status == ClipStatus.rendering
