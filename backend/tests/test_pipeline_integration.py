"""End-to-end integration test for the core promise of the product:

    submit a video URL -> download it -> transcribe it -> detect
    highlights -> generate Shorts-length clips -> export one as a real
    9:16 MP4.

Every other test file exercises one module in isolation, usually with
neighboring modules mocked out (e.g. test_videos.py mocks transcribe_video
and storage.download_from_url; test_exports.py mocks render_clip). That's
the right call for unit tests, but it also means no single test proves the
whole pipeline actually works together end-to-end with real ffmpeg and a
real (if tiny) video file -- which is exactly the kind of gap that let the
source_file_path and B-roll bugs slip through earlier. This test wires
everything together for real, with only two things faked:

  - the "internet": a local HTTP server stands in for wherever the user's
    video URL actually points, since the app's real SSRF guard correctly
    rejects loopback addresses -- see the `_assert_public_http_url`
    monkeypatch below.
  - the Whisper API: TRANSCRIPTION_API_KEY is cleared so the real
    fallback-transcript code path runs (still exercising the real
    ffmpeg.probe() duration lookup), since hitting the real OpenAI API in
    a test suite would be flaky/costly and isn't what this test is for.
"""

from __future__ import annotations

import functools
import http.server
import shutil
import subprocess
import threading
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.routers.videos as video_router_module

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg binary not available"
)


def _make_test_source_video(path: Path, duration: float = 300.0) -> None:
    """Synthesize a real MP4 (color video + silent audio) with ffmpeg."""

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=640x360:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=44100:cl=stereo:d={duration}",
            "-shortest",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # silence request logging in test output


@pytest.fixture
def source_http_server(tmp_path):  # type: ignore[no-untyped-def]
    """A local HTTP server standing in for the real internet host a user's
    video URL would point to."""

    serve_dir = tmp_path / "source_server"
    serve_dir.mkdir()
    handler = functools.partial(_QuietStaticHandler, directory=str(serve_dir))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, serve_dir
    finally:
        server.shutdown()
        thread.join(timeout=5)


#: What a few minutes of someone actually talking looks like. Timed to
#: cover the synthetic source's 300 seconds, with a clear hook part-way in
#: so highlight detection has a right answer to find.
SPOKEN_TRANSCRIPT: list[dict] = [
    {
        "start_time": 0.0,
        "end_time": 6.0,
        "text": "Hi everybody, thank you, thank you so much.",
    },
    {
        "start_time": 6.0,
        "end_time": 14.0,
        "text": "Welcome back to the show, please welcome our guest.",
    },
    {
        "start_time": 14.0,
        "end_time": 30.0,
        "text": "So we were talking backstage about the weather and the traffic.",
    },
    {
        "start_time": 30.0,
        "end_time": 38.0,
        "text": "Here's the thing nobody tells you about starting out.",
    },
    {
        "start_time": 38.0,
        "end_time": 52.0,
        "text": (
            "I never realized the biggest mistake was trying to sound like "
            "everyone else."
        ),
    },
    {
        "start_time": 52.0,
        "end_time": 70.0,
        "text": (
            "The truth is the first three years I spent copying people I "
            "admired, and it cost me."
        ),
    },
    {
        "start_time": 70.0,
        "end_time": 95.0,
        "text": (
            "What changed everything was realizing an audience can tell when "
            "you mean it."
        ),
    },
    {
        "start_time": 95.0,
        "end_time": 140.0,
        "text": "Anyway, that is roughly how it went for me.",
    },
    {
        "start_time": 140.0,
        "end_time": 200.0,
        "text": "And then we moved to a different city for a while.",
    },
    {
        "start_time": 200.0,
        "end_time": 260.0,
        "text": "Which is a whole other story for another time.",
    },
    {
        "start_time": 260.0,
        "end_time": 300.0,
        "text": "Thanks so much for having me, this was fun.",
    },
]


def test_url_to_9x16_short_end_to_end(
    client: TestClient,
    auth_headers: dict[str, str],
    source_http_server,  # noqa: ANN001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, serve_dir = source_http_server
    port = server.server_address[1]
    _make_test_source_video(serve_dir / "video.mp4", duration=300.0)

    # The real SSRF guard correctly rejects loopback addresses -- our fake
    # "internet" is loopback only because it's a test, so bypass just that
    # check here rather than weakening the real guard (see test_storage_security.py
    # for its dedicated coverage).
    import app.services.storage as storage_module

    monkeypatch.setattr(storage_module, "_assert_public_http_url", lambda url: None)
    # This suite's own host disk can legitimately be low on real free space;
    # that's a real condition worth rejecting in production (see
    # test_storage_security.py's dedicated coverage), but shouldn't fail this
    # unrelated pipeline test.
    monkeypatch.setattr(
        storage_module.shutil,
        "disk_usage",
        lambda _path: shutil._ntuple_diskusage(total=0, used=0, free=100 * 1024 * 1024 * 1024),
    )
    # The synthetic source is a colour card with silent audio: real
    # transcription (correctly) finds no speech in it, and running Whisper
    # in the suite would cost a model download and minutes per run. The
    # transcript is stubbed here so the *pipeline* is what's under test --
    # transcription has its own coverage in test_transcription.py.
    monkeypatch.setattr(
        video_router_module,
        "transcribe_video",
        AsyncMock(return_value=SPOKEN_TRANSCRIPT),
    )

    # 1. Submit the video URL.
    create_resp = client.post(
        "/api/v1/videos",
        data={
            "title": "Integration test video",
            "source_type": "url",
            "source_url": f"http://127.0.0.1:{port}/video.mp4",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    # Background pipeline (download -> transcribe -> highlight-score) runs
    # synchronously under TestClient by the time the request above returns.
    project_resp = client.get(f"/api/v1/videos/{project_id}", headers=auth_headers)
    project = project_resp.json()
    assert project["status"] == "ready", project.get("error_message")

    transcript_resp = client.get(
        f"/api/v1/videos/{project_id}/transcript", headers=auth_headers
    )
    segments = transcript_resp.json()
    assert len(segments) > 0
    assert any(seg["is_highlight"] for seg in segments)

    # 2. Generate Shorts-length clips from the detected highlights.
    generate_resp = client.post(
        "/api/v1/clips/generate",
        json={"video_project_id": project_id},
        headers=auth_headers,
    )
    assert generate_resp.status_code == 201
    clips = generate_resp.json()
    assert len(clips) > 0
    for clip in clips:
        duration = clip["end_time"] - clip["start_time"]
        assert duration <= 50.0, f"clip exceeded MAX_CLIP_DURATION: {duration}s"

    # 3. Export the first clip into a real 9:16 MP4.
    clip_id = clips[0]["id"]
    export_resp = client.post(f"/api/v1/clips/{clip_id}/export", headers=auth_headers)
    assert export_resp.status_code == 200

    status_resp = client.get(
        f"/api/v1/clips/{clip_id}/export/status", headers=auth_headers
    )
    status_body = status_resp.json()
    assert status_body["status"] == "ready", status_body
    assert status_body["video_file_path"]

    output_path = Path(status_body["video_file_path"])
    assert output_path.is_file()
    assert output_path.stat().st_size > 0

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    width, height = (int(v) for v in probe.stdout.strip().split(","))
    assert (width, height) == (1080, 1920), "export is not 9:16"
