"""Tests for the Export & Publish endpoints (/clips/{id}/export, /status, /download).

`render_clip` is monkeypatched at the app.routers.exports import site so
tests exercise the endpoint contract (status transitions, polling,
download gating) without depending on a real ffmpeg binary.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.models.clip import Clip, ClipCaptionStyle, ClipStatus
from app.models.transcript_segment import TranscriptSegment
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

    def test_download_via_query_param_token_succeeds(
        self,
        client: TestClient,
        db_session: Session,
        test_user: User,
        tmp_path: Path,
    ) -> None:
        video_file = tmp_path / "rendered.mp4"
        video_file.write_bytes(b"query param mp4 bytes")

        clip = _make_clip(
            db_session,
            test_user,
            status=ClipStatus.ready,
            video_file_path=str(video_file),
        )
        token = create_access_token({"sub": str(test_user.id)})
        # Without headers, authenticating solely via ?token=
        response = client.get(f"/api/v1/clips/{clip.id}/download?token={token}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert response.content == b"query param mp4 bytes"

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


class TestAutoBrollToggle:
    """The submit form's B-roll switch. Auto-sourcing runs at export, so
    the switch has to be honoured there or it does nothing at all."""

    def _clip_with_broll_setting(
        self, db_session: Session, user: User, *, auto_broll: bool
    ) -> Clip:
        project = VideoProject(
            user_id=user.id,
            title="B-roll project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            auto_broll=auto_broll,
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
            status=ClipStatus.draft,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)
        return clip

    def _export(self, client: TestClient, headers: dict[str, str], clip: Clip):  # type: ignore[no-untyped-def]
        with (
            patch("app.routers.exports.render_clip", new=_fake_render_success),
            patch("app.config.settings.BROLL_AUTO_ON_EXPORT", True),
            patch("app.config.settings.PEXELS_API_KEY", "test-key"),
            patch(
                "app.routers.exports.auto_source_broll",
                new=AsyncMock(return_value=[]),
            ) as sourcing,
        ):
            response = client.post(
                f"/api/v1/clips/{clip.id}/export", headers=headers
            )
        assert response.status_code == 200
        return sourcing

    def test_b_roll_is_sourced_when_the_video_asked_for_it(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        clip = self._clip_with_broll_setting(db_session, test_user, auto_broll=True)

        sourcing = self._export(client, auth_headers, clip)

        sourcing.assert_awaited_once()

    def test_b_roll_is_skipped_when_the_video_switched_it_off(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        clip = self._clip_with_broll_setting(db_session, test_user, auto_broll=False)

        sourcing = self._export(client, auth_headers, clip)

        sourcing.assert_not_awaited()


class TestCaptionTimeline:
    """/clips/{id}/captions: what the editor previews. It has to be the
    render path's own timeline, or the studio shows a silent short that
    exports fully subtitled."""

    def _clip_with_transcript(self, db_session: Session, user: User) -> Clip:
        project = VideoProject(
            user_id=user.id,
            title="Caption project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=5.0,
                end_time=9.0,
                text="Nobody tells you how simple this really is",
                is_highlight=True,
            )
        )
        clip = Clip(
            video_project_id=project.id,
            user_id=user.id,
            title="Caption clip",
            start_time=5.0,
            end_time=15.0,
            order_index=0,
            status=ClipStatus.draft,
            caption_style=ClipCaptionStyle.hormozi,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)
        return clip

    def test_captions_come_from_the_transcript_not_just_caption_text(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        clip = self._clip_with_transcript(db_session, test_user)
        assert clip.caption_text is None, "the point: nothing typed by hand"

        response = client.get(
            f"/api/v1/clips/{clip.id}/captions", headers=auth_headers
        )

        assert response.status_code == 200
        body = response.json()
        assert body["style"] == "hormozi"
        assert body["events"], "a clip with a transcript has captions to show"
        # Timed from the clip's own start, so the editor can match them
        # against its playhead.
        assert body["events"][0]["start_time"] == 0.0
        assert all(event["end_time"] <= 10.0 for event in body["events"])
        assert "nobody" in " ".join(e["text"] for e in body["events"]).lower()

    def test_a_word_highlighting_style_lights_one_word_at_a_time(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        clip = self._clip_with_transcript(db_session, test_user)

        response = client.get(
            f"/api/v1/clips/{clip.id}/captions", headers=auth_headers
        )

        events = response.json()["events"]
        highlighted = [e["active_word"] for e in events if e["active_word"] is not None]
        assert highlighted, "Hormozi highlights the spoken word; none were marked"
        assert highlighted == sorted(highlighted) or len(set(highlighted)) > 1

    def test_a_style_without_highlighting_returns_whole_captions(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        test_user: User,
    ) -> None:
        clip = self._clip_with_transcript(db_session, test_user)
        clip.caption_style = ClipCaptionStyle.minimal
        db_session.commit()

        response = client.get(
            f"/api/v1/clips/{clip.id}/captions", headers=auth_headers
        )

        events = response.json()["events"]
        assert events
        assert all(event["active_word"] is None for event in events)

    def test_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)

        response = client.get(f"/api/v1/clips/{clip.id}/captions", headers=auth_headers)

        assert response.status_code == 404


class TestFraming:
    """/clips/{id}/framing: the crop windows the Speaker Focus preview
    applies, so the editor shows what the export will render.

    `compute_speaker_framing` is patched at the router's import site --
    the detection itself is covered in test_reframe.py against real
    footage; what matters here is the endpoint contract."""

    def _project_with_source(self, db_session: Session, user: User) -> Clip:
        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / "framing.mp4"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_bytes(b"source video bytes")

        project = VideoProject(
            user_id=user.id,
            title="Framing project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/framing.mp4",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        clip = Clip(
            video_project_id=project.id,
            user_id=user.id,
            title="Draft clip",
            start_time=5.0,
            end_time=45.0,
            order_index=0,
            status=ClipStatus.draft,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)
        return clip

    def test_windows_are_normalised_to_the_source_frame(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_user: User,
        db_session: Session,
    ) -> None:
        from app.services.reframe import SpeakerFraming, SpeakerWindow

        clip = self._project_with_source(db_session, test_user)
        framing = SpeakerFraming(
            source_width=1920,
            source_height=1080,
            crop_width=384,
            crop_height=683,
            windows=(
                SpeakerWindow(start_time=0.0, x=960, y=270),
                SpeakerWindow(start_time=12.5, x=192, y=200, at_cut=False),
            ),
        )

        with patch(
            "app.routers.exports.compute_speaker_framing", return_value=framing
        ) as compute:
            response = client.get(
                f"/api/v1/clips/{clip.id}/framing", headers=auth_headers
            )

        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "speaker_focus"
        assert body["windows"][0] == {
            "start_time": 0.0,
            "x": 0.5,
            "y": 0.25,
            "width": 0.2,
            "height": pytest.approx(683 / 1080),
            "at_cut": True,
        }
        assert body["windows"][1]["start_time"] == 12.5
        assert body["windows"][1]["at_cut"] is False, (
            "a mid-shot move must tell the preview to ease, not snap"
        )
        # Analysed over the clip's own window, not the whole source.
        assert compute.call_args.args[1:3] == (5.0, 40.0)

    def test_footage_with_no_subject_reports_unavailable(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_user: User,
        db_session: Session,
    ) -> None:
        clip = self._project_with_source(db_session, test_user)

        with patch("app.routers.exports.compute_speaker_framing", return_value=None):
            response = client.get(
                f"/api/v1/clips/{clip.id}/framing", headers=auth_headers
            )

        assert response.status_code == 200
        assert response.json() == {
            "clip_id": clip.id,
            "mode": "unavailable",
            "windows": [],
            "split_sections": [],
        }

    def test_split_screen_stretches_come_back_with_their_panes(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_user: User,
        db_session: Session,
    ) -> None:
        """Two people talking: the preview needs the panes, in the same
        normalised coordinates as the single-speaker windows, so it can
        stack them the way the export will."""

        from app.services.reframe import (
            SpeakerFraming,
            SpeakerWindow,
            SplitFraming,
            SplitSection,
        )

        clip = self._project_with_source(db_session, test_user)
        framing = SpeakerFraming(
            source_width=1920,
            source_height=1080,
            crop_width=384,
            crop_height=683,
            windows=(SpeakerWindow(start_time=0.0, x=960, y=270),),
            split=SplitFraming(
                pane_count=2,
                crop_width=960,
                crop_height=540,
                sections=(
                    SplitSection(
                        start_time=0.0,
                        end_time=12.0,
                        panes=(
                            SpeakerWindow(start_time=0.0, x=0, y=0),
                            SpeakerWindow(start_time=0.0, x=960, y=540),
                        ),
                    ),
                ),
            ),
        )

        with patch(
            "app.routers.exports.compute_speaker_framing", return_value=framing
        ):
            response = client.get(
                f"/api/v1/clips/{clip.id}/framing", headers=auth_headers
            )

        assert response.status_code == 200
        section = response.json()["split_sections"][0]
        assert (section["start_time"], section["end_time"]) == (0.0, 12.0)
        # Panes carry the split's own crop size, not the single window's.
        assert section["panes"] == [
            {
                "start_time": 0.0,
                "x": 0.0,
                "y": 0.0,
                "width": 0.5,
                "height": 0.5,
                "at_cut": True,
            },
            {
                "start_time": 0.0,
                "x": 0.5,
                "y": 0.5,
                "width": 0.5,
                "height": 0.5,
                "at_cut": True,
            },
        ]

    def test_an_exported_clip_is_already_framed(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_user: User,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        """A ready clip's preview *is* the 9:16 export; cropping it again
        would zoom in on a crop."""

        rendered = tmp_path / "rendered.mp4"
        rendered.write_bytes(b"rendered clip bytes")
        clip = _make_clip(
            db_session,
            test_user,
            status=ClipStatus.ready,
            video_file_path=str(rendered),
        )

        with patch("app.routers.exports.compute_speaker_framing") as compute:
            response = client.get(
                f"/api/v1/clips/{clip.id}/framing", headers=auth_headers
            )

        assert response.status_code == 200
        assert response.json()["mode"] == "rendered"
        compute.assert_not_called()

    def test_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        clip = _make_clip(db_session, other_user)

        response = client.get(f"/api/v1/clips/{clip.id}/framing", headers=auth_headers)

        assert response.status_code == 404

    def test_missing_source_file_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_user: User,
        db_session: Session,
    ) -> None:
        clip = _make_clip(db_session, test_user, status=ClipStatus.draft)

        response = client.get(f"/api/v1/clips/{clip.id}/framing", headers=auth_headers)

        assert response.status_code == 404
