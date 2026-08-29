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

import pytest
from fastapi.testclient import TestClient

from app.config import settings

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
    # Exercise the real fallback-transcript path (no paid Whisper call in tests).
    monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "")

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
