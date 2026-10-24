"""Tests for YouTube Shorts caption package generation and direct Short upload endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clip import Clip, ClipCaptionStyle, ClipFraming, ClipStatus
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus


class TestYouTubeCaptionPackageEndpoint:
    def test_get_youtube_caption_package_returns_metadata_and_content(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        project = VideoProject(
            user_id=test_user.id,
            title="AI Productivity Secrets",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            duration_seconds=30.0,
        )
        db_session.add(project)
        db_session.flush()

        db_session.add_all(
            [
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=0.0,
                    end_time=6.0,
                    text="Here is the secret nobody tells you about AI productivity.",
                    is_highlight=True,
                    highlight_score=0.9,
                ),
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=6.0,
                    end_time=15.0,
                    text="Automating repetitive workflows saves ten hours every week.",
                    is_highlight=False,
                    highlight_score=0.7,
                ),
            ]
        )
        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Here is the secret nobody tells you about AI",
            start_time=0.0,
            end_time=15.0,
            order_index=0,
            status=ClipStatus.ready,
            caption_style=ClipCaptionStyle.hormozi,
            framing_mode=ClipFraming.speaker_focus,
            virality_score=85.0,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        resp = client.get(
            f"/api/v1/clips/{clip.id}/youtube-caption?tone=viral",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["clip_id"] == clip.id
        assert "#Shorts" in data["youtube_title"]
        assert len(data["youtube_title"]) <= 100
        assert "AI productivity" in data["caption_text"]
        assert len(data["timed_captions"]) >= 1
        assert "-->" in data["srt_content"]
        assert "#Shorts" in data["hashtags"]
        assert data["specs_check"]["is_youtube_short_ready"] is True
        assert data["specs_check"]["aspect_ratio"] == "9:16 (Vertical)"

    def test_post_youtube_caption_package_applies_custom_caption(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        project = VideoProject(
            user_id=test_user.id,
            title="Custom Short",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.flush()

        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Custom Short Clip",
            start_time=0.0,
            end_time=20.0,
            order_index=0,
            status=ClipStatus.draft,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        resp = client.post(
            f"/api/v1/clips/{clip.id}/youtube-caption",
            json={
                "tone": "educational",
                "include_hashtags": True,
                "include_timestamps": True,
                "custom_caption_text": (
                    "Three counterintuitive lessons from building micro-SaaS products."
                ),
                "apply_caption_to_clip": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tone"] == "educational"
        assert "micro-SaaS" in data["caption_text"]

        db_session.refresh(clip)
        assert (
            clip.caption_text
            == "Three counterintuitive lessons from building micro-SaaS products."
        )


class TestUploadShortEndpoint:
    def test_upload_short_creates_ready_project_clip_and_youtube_package(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        fake_segments = [
            {
                "start_time": 0.0,
                "end_time": 12.0,
                "text": "Why do 90% of creators miss this simple YouTube Shorts hook?",
            },
            {
                "start_time": 12.0,
                "end_time": 24.0,
                "text": "Start with a visual change in the first two seconds to boost retention.",
            },
        ]
        with (
            patch(
                "app.routers.videos.transcribe_video",
                new=AsyncMock(return_value=fake_segments),
            ),
            patch("app.routers.videos._probe_video_duration", return_value=24.0),
            patch("app.routers.videos.render_clip"),
        ):
            files = {"file": ("my_short.mp4", b"fake short video bytes", "video/mp4")}
            data = {
                "title": "YouTube Shorts Hook Secret",
                "tone": "viral",
                "caption_style": "hormozi",
                "framing_mode": "speaker_focus",
                "auto_render": "true",
            }
            resp = client.post(
                "/api/v1/videos/upload-short",
                data=data,
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["project"]["title"] == "YouTube Shorts Hook Secret"
        assert body["project"]["status"] == "ready"
        assert body["clip"]["end_time"] == 24.0
        assert "#Shorts" in body["youtube_package"]["youtube_title"]
        assert "90% of creators" in body["youtube_package"]["caption_text"]
        assert body["youtube_package"]["specs_check"]["is_youtube_short_ready"] is True
