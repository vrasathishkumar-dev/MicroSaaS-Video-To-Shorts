"""Tests for /api/v1/clips/* endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.broll_asset import BrollAsset, BrollSource
from app.models.clip import Clip, ClipCaptionStyle, ClipFraming
from app.models.transcript_segment import TranscriptSegment
from app.models.user import User
from app.models.video_project import (
    ClipLength,
    SourceType,
    VideoProject,
    VideoProjectStatus,
)


def _make_ready_project_with_highlights(
    db_session: Session,
    user: User,
    n_highlights: int = 2,
    n_plain: int = 1,
    **project_options,
) -> VideoProject:
    project = VideoProject(
        user_id=user.id,
        title="Ready project",
        source_type=SourceType.upload,
        status=VideoProjectStatus.ready,
        **project_options,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Highlight segments are 45s long and spaced 55s apart -- both already
    # within clip_service's MIN/MAX_CLIP_DURATION target window, and far
    # enough apart that clip generation's overlap-merging won't collapse
    # separate highlights into one clip.
    t = 0.0
    for i in range(n_highlights):
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=t,
                end_time=t + 45.0,
                text=f"Highlight segment {i}.",
                is_highlight=True,
                highlight_score=0.9,
            )
        )
        t += 55.0
    for i in range(n_plain):
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=t,
                end_time=t + 10.0,
                text=f"Plain segment {i}.",
                is_highlight=False,
                highlight_score=0.1,
            )
        )
        t += 10.0
    db_session.commit()
    return project


class TestGenerate:
    def test_generate_from_highlights(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=2)

        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        assert response.status_code == 201
        clips = response.json()
        assert len(clips) == 2
        assert all(c["status"] == "draft" for c in clips)
        assert all(c["video_project_id"] == project.id for c in clips)
        # Ordered by start_time -> order_index 0, 1
        assert [c["order_index"] for c in clips] == [0, 1]

    def test_generate_expands_short_highlight_to_min_duration(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """A single-sentence highlight (a few seconds, as Whisper produces)
        should be expanded to a real Short-length clip, not left at its raw
        transcript-segment length."""

        project = VideoProject(
            user_id=test_user.id,
            title="Long ready project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=100.0,
                end_time=102.0,
                text="Short highlight.",
                is_highlight=True,
                highlight_score=0.95,
            )
        )
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=102.0,
                end_time=300.0,
                text="Rest of the video.",
                is_highlight=False,
                highlight_score=0.1,
            )
        )
        db_session.commit()

        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        assert response.status_code == 201
        clip = response.json()[0]
        duration = clip["end_time"] - clip["start_time"]
        assert 30.0 <= duration <= 50.0

    def test_generate_scattered_highlights_do_not_cascade_into_one_clip(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """Regression test: a video with many highlights spread every ~30s
        (typical of a long real video, where ~20% of all segments get
        flagged) previously cascaded -- each highlight's +/-20s padding
        bled into the next one's, chaining the whole video into one
        multi-minute "clip" instead of several real Shorts."""

        project = VideoProject(
            user_id=test_user.id,
            title="Long ready project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # 10 short highlighted "moments" (2 touching sentences each), one
        # every 30s across a 300s video -- dense enough that the old
        # padding-then-merge approach chained them all into one clip.
        t = 0.0
        for i in range(10):
            db_session.add(
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=t,
                    end_time=t + 1.0,
                    text=f"Highlight {i}a.",
                    is_highlight=True,
                    highlight_score=0.9,
                )
            )
            db_session.add(
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=t + 1.0,
                    end_time=t + 2.0,
                    text=f"Highlight {i}b.",
                    is_highlight=True,
                    highlight_score=0.9,
                )
            )
            t += 30.0
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=t,
                end_time=t + 10.0,
                text="Tail of the video.",
                is_highlight=False,
                highlight_score=0.1,
            )
        )
        db_session.commit()

        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        assert response.status_code == 201
        clips = sorted(response.json(), key=lambda c: c["start_time"])

        assert len(clips) > 1, "10 scattered highlights collapsed into one clip"
        for clip in clips:
            duration = clip["end_time"] - clip["start_time"]
            assert duration <= 50.0, f"clip exceeded MAX_CLIP_DURATION: {duration}s"
        for earlier, later in zip(clips, clips[1:], strict=False):
            assert earlier["end_time"] <= later["start_time"], "clips overlap"

    def test_generate_requires_ready_status(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = VideoProject(
            user_id=test_user.id,
            title="Not ready",
            source_type=SourceType.upload,
            status=VideoProjectStatus.transcribing,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_generate_nonexistent_project_404(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": 999999},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_generate_other_users_project_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, other_user)
        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestGeneratedClipsFollowTheSubmission:
    """What the submit form asked for has to show up in the clips -- the
    options are chosen before there is anything to edit, so if generation
    ignores them the user never gets what they asked for."""

    def test_clips_inherit_the_framing_and_caption_style(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(
            db_session,
            test_user,
            n_highlights=2,
            framing_mode=ClipFraming.dynamic_blur,
            caption_style=ClipCaptionStyle.neon,
        )

        response = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )

        assert response.status_code == 201
        clips = response.json()
        assert clips
        assert all(clip["framing_mode"] == "dynamic_blur" for clip in clips)
        assert all(clip["caption_style"] == "neon" for clip in clips)

    def test_fast_shorts_are_cut_shorter_than_in_depth_ones(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """Same highlights, different requested length: the windows the
        generator cuts have to differ, or the setting means nothing."""

        fast = _make_ready_project_with_highlights(
            db_session, test_user, n_highlights=1, target_clip_length=ClipLength.fast
        )
        in_depth = _make_ready_project_with_highlights(
            db_session, test_user, n_highlights=1, target_clip_length=ClipLength.in_depth
        )

        def generate(project: VideoProject) -> float:
            response = client.post(
                "/api/v1/clips/generate",
                json={"video_project_id": project.id},
                headers=auth_headers,
            )
            assert response.status_code == 201
            clip = response.json()[0]
            return clip["end_time"] - clip["start_time"]

        fast_duration = generate(fast)
        in_depth_duration = generate(in_depth)

        assert fast_duration <= 30.0, fast_duration
        assert in_depth_duration > fast_duration


class TestListAndGet:
    def test_list_clips_filtered_by_video_project(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project_a = _make_ready_project_with_highlights(db_session, test_user, n_highlights=2)
        project_b = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)

        client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project_a.id},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project_b.id},
            headers=auth_headers,
        )

        all_resp = client.get("/api/v1/clips", headers=auth_headers)
        assert all_resp.json()["total"] == 3

        filtered_resp = client.get(
            "/api/v1/clips",
            params={"video_project_id": project_a.id},
            headers=auth_headers,
        )
        assert filtered_resp.json()["total"] == 2
        assert all(
            c["video_project_id"] == project_a.id for c in filtered_resp.json()["items"]
        )

    def test_get_clip(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_id = gen_resp.json()[0]["id"]

        response = client.get(f"/api/v1/clips/{clip_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == clip_id

    def test_get_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        project = _make_ready_project_with_highlights(
            db_session, other_user, n_highlights=0, n_plain=0
        )
        clip = Clip(
            video_project_id=project.id,
            user_id=other_user.id,
            title="Not yours",
            start_time=0.0,
            end_time=10.0,
            order_index=0,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        response = client.get(f"/api/v1/clips/{clip.id}", headers=auth_headers)
        assert response.status_code == 404


class TestUpdate:
    def test_update_clip_trim_and_caption(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_id = gen_resp.json()[0]["id"]

        response = client.put(
            f"/api/v1/clips/{clip_id}",
            json={"title": "New Title", "start_time": 1.5, "end_time": 8.0, "caption_text": "Hi!"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "New Title"
        assert body["start_time"] == 1.5
        assert body["end_time"] == 8.0
        assert body["caption_text"] == "Hi!"

    def test_update_framing_and_caption_style(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """The studio's framing toggle and caption picker write here. They
        have to persist, because the renderer reads them back at export --
        a choice that only lives in the browser is a choice the finished
        short doesn't have."""

        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_id = gen_resp.json()[0]["id"]
        # A freshly generated clip renders as speaker focus with Hormozi
        # captions unless the user says otherwise.
        assert gen_resp.json()[0]["framing_mode"] == "speaker_focus"
        assert gen_resp.json()[0]["caption_style"] == "hormozi"

        response = client.put(
            f"/api/v1/clips/{clip_id}",
            json={"framing_mode": "dynamic_blur", "caption_style": "karaoke"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["framing_mode"] == "dynamic_blur"
        assert response.json()["caption_style"] == "karaoke"

        reread = client.get(f"/api/v1/clips/{clip_id}", headers=auth_headers)
        assert reread.json()["framing_mode"] == "dynamic_blur"
        assert reread.json()["caption_style"] == "karaoke"

    def test_update_rejects_a_framing_mode_the_renderer_cannot_honour(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_id = gen_resp.json()[0]["id"]

        response = client.put(
            f"/api/v1/clips/{clip_id}",
            json={"framing_mode": "cinematic_zoom"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_update_clip_partial(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip = gen_resp.json()[0]
        clip_id = clip["id"]
        original_start = clip["start_time"]

        response = client.put(
            f"/api/v1/clips/{clip_id}",
            json={"caption_text": "Only caption changed"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["caption_text"] == "Only caption changed"
        assert body["start_time"] == original_start

    def test_update_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, other_user, n_highlights=1)
        clip = Clip(
            video_project_id=project.id,
            user_id=other_user.id,
            title="Not yours",
            start_time=0.0,
            end_time=10.0,
            order_index=0,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        response = client.put(
            f"/api/v1/clips/{clip.id}",
            json={"title": "Hijacked"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestReorder:
    def test_reorder_clip(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=2)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_id = gen_resp.json()[0]["id"]

        response = client.patch(
            f"/api/v1/clips/{clip_id}/reorder",
            json={"order_index": 5},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["order_index"] == 5


class TestDelete:
    def test_delete_clip_cascades_broll_assets(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=1)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_id = gen_resp.json()[0]["id"]

        broll = BrollAsset(
            clip_id=clip_id,
            source=BrollSource.pexels,
            source_asset_id="abc123",
            asset_url="https://example.com/broll.mp4",
            keyword="nature",
            position_start=0.0,
            position_end=3.0,
        )
        db_session.add(broll)
        db_session.commit()
        broll_id = broll.id

        response = client.delete(f"/api/v1/clips/{clip_id}", headers=auth_headers)
        assert response.status_code == 204

        # The clip itself is gone.
        get_resp = client.get(f"/api/v1/clips/{clip_id}", headers=auth_headers)
        assert get_resp.status_code == 404

        # Its broll_assets were cascade-deleted at the DB level too (this
        # is the actual FK ON DELETE CASCADE, not ORM cascade -- the ORM
        # never emits a child DELETE for `passive_deletes=True`).
        db_session.expire_all()
        remaining = db_session.query(BrollAsset).filter(BrollAsset.id == broll_id).first()
        assert remaining is None

    def test_delete_other_users_clip_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        db_session: Session,
        other_user: User,
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, other_user, n_highlights=1)
        clip = Clip(
            video_project_id=project.id,
            user_id=other_user.id,
            title="Not yours",
            start_time=0.0,
            end_time=10.0,
            order_index=0,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        response = client.delete(f"/api/v1/clips/{clip.id}", headers=auth_headers)
        assert response.status_code == 404


class TestCascadeFromVideoProject:
    def test_deleting_video_project_cascades_clips(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        project = _make_ready_project_with_highlights(db_session, test_user, n_highlights=2)
        gen_resp = client.post(
            "/api/v1/clips/generate",
            json={"video_project_id": project.id},
            headers=auth_headers,
        )
        clip_ids = [c["id"] for c in gen_resp.json()]
        assert len(clip_ids) == 2

        delete_resp = client.delete(f"/api/v1/videos/{project.id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        db_session.expire_all()
        remaining = db_session.query(Clip).filter(Clip.id.in_(clip_ids)).all()
        assert remaining == []
