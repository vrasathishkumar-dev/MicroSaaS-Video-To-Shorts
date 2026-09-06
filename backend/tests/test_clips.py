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
from app.services.clip_service import (
    _HARD_MAX_CLIP_DURATION,
    _SENTENCE_BOUNDARY_ALLOWANCE_SECONDS,
    CLIP_LENGTH_TARGETS,
    _clamp_start_to_boundary,
    _extend_to_sentence_boundary,
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


def _segment(start: float, end: float, text: str) -> TranscriptSegment:
    """A bare (unpersisted) TranscriptSegment -- _extend_to_sentence_boundary
    only reads attributes, so no db_session/project is needed for these
    pure-function tests."""

    return TranscriptSegment(
        video_project_id=1, start_time=start, end_time=end, text=text
    )


class TestExtendToSentenceBoundary:
    """Unit coverage for the sentence-boundary edge selection itself --
    the pipeline-level tests below cover it wired into clip generation."""

    def test_extends_past_the_raw_duration_edge_to_finish_the_sentence(self) -> None:
        segments = [
            _segment(0.0, 5.0, "Setup line that keeps talking"),
            _segment(5.0, 9.0, "and finally reaches the point."),
            _segment(9.0, 20.0, "Next unrelated sentence starts here."),
        ]
        # The raw duration edge (7.0) lands mid-way through the second
        # segment; the sentence doesn't finish until 9.0.
        start, end = _extend_to_sentence_boundary(
            start=0.0,
            end=7.0,
            segments=segments,
            floor=0.0,
            ceiling=20.0,
            allowed_duration=30.0,
        )
        assert (start, end) == (0.0, 9.0)

    def test_extension_bounded_by_allowed_duration_leaves_edge_unchanged(self) -> None:
        segments = [
            _segment(0.0, 5.0, "Opening line."),
            _segment(
                5.0,
                55.0,
                "one continuous sentence that runs on and on until it ends.",
            ),
        ]
        # The only terminal boundary (55.0) is far past what
        # allowed_duration permits from this window -- must not reach for
        # it, and must not shrink the window either.
        start, end = _extend_to_sentence_boundary(
            start=0.0,
            end=20.0,
            segments=segments,
            floor=0.0,
            ceiling=60.0,
            allowed_duration=30.0,
        )
        assert (start, end) == (0.0, 20.0)

    def test_never_crosses_the_neighbouring_clips_floor_or_ceiling(self) -> None:
        segments = [
            _segment(0.0, 10.0, "Sentence before the window."),
            _segment(10.0, 20.0, "Sentence inside the window."),
            _segment(20.0, 30.0, "Sentence after the window."),
        ]
        start, end = _extend_to_sentence_boundary(
            start=10.0,
            end=18.0,
            segments=segments,
            floor=10.0,
            ceiling=20.0,
            allowed_duration=30.0,
        )
        assert start >= 10.0
        assert end <= 20.0

    def test_no_terminal_punctuation_reachable_leaves_edges_unchanged(self) -> None:
        segments = [
            _segment(2.0, 10.0, "no punctuation at all here"),
            _segment(10.0, 20.0, "still nothing terminal in this transcript"),
        ]
        start, end = _extend_to_sentence_boundary(
            start=2.0,
            end=15.0,
            segments=segments,
            floor=0.0,
            ceiling=20.0,
            allowed_duration=30.0,
        )
        assert (start, end) == (2.0, 15.0)


class TestClampStartToBoundary:
    """Unit coverage for the post-extend hard-cap clamp -- QA's regression
    (start_time landing mid-segment via raw subtraction)."""

    def test_lands_on_nearest_reachable_sentence_boundary_not_raw_subtraction(
        self,
    ) -> None:
        # Ten contiguous 8s segments (0-80), each its own sentence -- the
        # exact QA repro fixture. allowed_duration=60, end_time=72, so raw
        # subtraction would give start_time=12.0 (mid-segment); the
        # nearest reachable sentence-terminal start at/after 12.0 is 16.0.
        segments = [
            _segment(i * 8.0, i * 8.0 + 8.0, f"Highlight segment {i}.")
            for i in range(10)
        ]
        start = _clamp_start_to_boundary(
            start_time=8.0,
            end_time=72.0,
            segments=segments,
            floor=0.0,
            allowed_duration=60.0,
        )
        assert start == 16.0
        assert 72.0 - start <= 60.0

    def test_falls_back_to_a_plain_segment_start_when_no_sentence_boundary_in_range(
        self,
    ) -> None:
        # No terminal punctuation anywhere -- every segment start is a
        # plain boundary, not a sentence boundary, so the fallback tier
        # must still land on a real segment edge rather than mid-segment.
        segments = [
            _segment(i * 8.0, i * 8.0 + 8.0, f"segment {i} with no punctuation")
            for i in range(10)
        ]
        start = _clamp_start_to_boundary(
            start_time=8.0,
            end_time=72.0,
            segments=segments,
            floor=0.0,
            allowed_duration=60.0,
        )
        assert start in {i * 8.0 for i in range(10)}
        assert 72.0 - start <= 60.0

    def test_never_returns_a_boundary_that_produces_a_near_empty_clip(self) -> None:
        # end_time (80.0) is itself a segment start -- an admissible
        # position by `min_start <= s <= end_time` alone, but picking it
        # would produce a zero-length clip. With no other boundary
        # reachable in [min_start, end_time - _MIN_SNAPPED_DURATION], the
        # function must fall back to min_start rather than that
        # zero-length boundary.
        segments = [
            _segment(0.0, 20.0, "Segment zero."),
            _segment(20.0, 40.0, "Segment one."),
            _segment(40.0, 60.0, "Segment two."),
            _segment(60.0, 80.0, "Segment three."),
            _segment(80.0, 100.0, "Segment four."),
        ]
        start = _clamp_start_to_boundary(
            start_time=0.0,
            end_time=80.0,
            segments=segments,
            floor=0.0,
            allowed_duration=15.0,
        )
        assert start == 65.0
        assert 80.0 - start == 15.0


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

    def test_generate_extends_fast_clip_to_sentence_end_within_bounded_allowance(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """A "fast" clip whose sentence finishes a few seconds past both the
        duration budget and the pause-snap should still land on the
        sentence's end -- bounded by the allowance, not the raw edges."""

        project = VideoProject(
            user_id=test_user.id,
            title="Fast project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            target_clip_length=ClipLength.fast,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # 32s of continuous, open-ended speech (no terminal punctuation) --
        # longer than fast's 30s maximum, so _pad_clusters trims it down to
        # a 30s centered window that cuts off mid-sentence.
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=0.0,
                end_time=32.0,
                text="Highlight that keeps going without stopping for a while",
                is_highlight=True,
                highlight_score=0.9,
            )
        )
        # The sentence actually finishes here, 2s past the trimmed window.
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=32.0,
                end_time=34.0,
                text="and that's the point.",
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

        fast_maximum = CLIP_LENGTH_TARGETS[ClipLength.fast][1]
        assert clip["end_time"] == 34.0
        assert duration > fast_maximum, "did not extend to finish the sentence"
        assert duration <= fast_maximum + _SENTENCE_BOUNDARY_ALLOWANCE_SECONDS
        assert duration <= _HARD_MAX_CLIP_DURATION

    def test_generate_never_exceeds_the_hard_60s_cap_even_after_snap_widens_it(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """_snap_to_speech can widen a window by up to
        2 * _SNAP_TOLERANCE_SECONDS on its own. For "in_depth" clips the
        bounded allowance is entirely absorbed by the 60s hard cap
        (maximum is already 60), leaving no room to absorb that widening --
        the pipeline must still bring the clip back under 60s."""

        project = VideoProject(
            user_id=test_user.id,
            title="In-depth project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            target_clip_length=ClipLength.in_depth,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        # Ten adjacent 8s highlighted segments (0-80s) merge into one
        # 80s cluster, longer than in_depth's 60s maximum -- centered
        # trim lands on (10, 70), which _snap_to_speech then widens to
        # (8, 72) via nearby segment boundaries.
        for i in range(10):
            db_session.add(
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=i * 8.0,
                    end_time=i * 8.0 + 8.0,
                    text=f"Highlight segment {i}.",
                    is_highlight=True,
                    highlight_score=0.9,
                )
            )
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=80.0,
                end_time=88.0,
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
        clip = response.json()[0]
        duration = clip["end_time"] - clip["start_time"]
        assert duration <= _HARD_MAX_CLIP_DURATION

        # Regression coverage for the QA-reported bug: the clamp that
        # enforces the hard cap must land start_time on a real boundary
        # (here, a multiple of 8.0 -- every segment starts on one), not
        # wherever raw `end_time - allowed_duration` subtraction falls
        # (12.0, mid-segment). The nearest reachable sentence-terminal
        # start at/after end_time - allowed_duration (72 - 60 = 12) is
        # 16.0, giving a 56s clip.
        assert clip["start_time"] == 16.0
        assert clip["end_time"] == 72.0
        assert duration == 56.0

        # The clip's title must come from a segment inside the final
        # window, not the anchor highlight ([0.0, 8.0]) that this clamp
        # pushed outside of it -- _fallback_title_source falls back to the
        # first in-window segment (starting at 16.0), unchanged by
        # _auto_title since it's already short.
        assert clip["title"] == "Highlight segment 2."

    def test_generate_with_no_terminal_punctuation_still_produces_valid_clips(
        self, client: TestClient, auth_headers: dict[str, str], db_session: Session, test_user
    ) -> None:
        """No sentence-terminal boundary anywhere in the transcript: the
        fallback chain (sentence boundary -> snap-to-speech -> raw edges)
        must still produce non-empty, non-overlapping clips rather than
        erroring or degenerating."""

        project = VideoProject(
            user_id=test_user.id,
            title="No punctuation project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        t = 0.0
        for i in range(2):
            db_session.add(
                TranscriptSegment(
                    video_project_id=project.id,
                    start_time=t,
                    end_time=t + 45.0,
                    text=f"highlight segment {i} without any punctuation",
                    is_highlight=True,
                    highlight_score=0.9,
                )
            )
            t += 55.0
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=t,
                end_time=t + 10.0,
                text="plain segment without any punctuation",
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

        assert len(clips) == 2
        for clip in clips:
            assert clip["end_time"] > clip["start_time"], "empty or inverted clip"
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
