"""Tests for the real ffmpeg render pipeline (app.services.video_render).

These exercise render_clip() end-to-end against the actual ffmpeg binary
(unlike test_exports.py, which monkeypatches render_clip entirely to test
the endpoint contract) -- specifically to cover source_file_path
resolution, which the endpoint-level mocks can't catch since they never
call the real rendering code.
"""

from __future__ import annotations

import functools
import http.server
import shutil
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.broll_asset import BrollAsset, BrollSource
from app.models.clip import Clip, ClipStatus
from app.models.user import User
from app.models.video_project import SourceType, VideoProject, VideoProjectStatus
from app.services import video_render as video_render_module
from app.services.video_render import render_clip

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg binary not available"
)


def _make_test_source_video(path: Path, duration: float = 3.0) -> None:
    """Synthesize a tiny real MP4 (color video + silent audio) with ffmpeg."""

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
def broll_http_server(tmp_path):  # type: ignore[no-untyped-def]
    """A tiny local HTTP server standing in for Pexels/Pixabay, so
    render_clip's B-roll download step can be exercised without hitting
    the real internet."""

    serve_dir = tmp_path / "broll_server"
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


class TestRenderClip:
    def test_render_resolves_source_relative_to_upload_root(
        self, db_session: Session, test_user: User
    ) -> None:
        """Regression test: source_file_path is stored relative to
        UPLOAD_ROOT (e.g. "videos/abc.mp4"), same convention as every other
        consumer (transcription, clip preview). render_clip must resolve it
        the same way instead of treating it as a literal filesystem path --
        otherwise every export fails before ffmpeg ever runs."""

        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / "source.mp4"
        _make_test_source_video(source_file)

        project = VideoProject(
            user_id=test_user.id,
            title="Render project",
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
            title="Clip",
            start_time=0.0,
            end_time=2.0,
            order_index=0,
            status=ClipStatus.rendering,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        render_clip(clip.id)

        db_session.refresh(clip)
        assert clip.status == ClipStatus.ready
        assert clip.video_file_path

        output_path = Path(clip.video_file_path)
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

    def test_render_downloads_and_composites_remote_broll(
        self,
        db_session: Session,
        test_user: User,
        broll_http_server,  # noqa: ANN001
    ) -> None:
        """Regression test: every real BrollAsset.asset_url is a remote
        Pexels/Pixabay http(s) URL (see BrollInsertRequest's validator) --
        render_clip must download it before compositing, or B-roll silently
        never appears in any export (see _resolve_broll_path)."""

        import app.services.storage as storage_module

        server, serve_dir = broll_http_server
        port = server.server_address[1]

        source_file = storage_module.UPLOAD_ROOT / "videos" / "source.mp4"
        _make_test_source_video(source_file, duration=6.0)
        _make_test_source_video(serve_dir / "broll.mp4", duration=2.0)

        project = VideoProject(
            user_id=test_user.id,
            title="Render with broll",
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
            title="Clip",
            start_time=0.0,
            end_time=5.0,
            order_index=0,
            status=ClipStatus.rendering,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        broll_asset = BrollAsset(
            clip_id=clip.id,
            source=BrollSource.pexels,
            source_asset_id="1",
            asset_url=f"http://127.0.0.1:{port}/broll.mp4",
            keyword="test",
            position_start=0.0,
            position_end=2.0,
        )
        db_session.add(broll_asset)
        db_session.commit()

        original_download = video_render_module._download_remote_broll
        captured_results = []

        def _spy_download(url: str, dest_dir: Path):  # type: ignore[no-untyped-def]
            result = original_download(url, dest_dir)
            captured_results.append(result)
            return result

        with patch.object(
            video_render_module, "_download_remote_broll", side_effect=_spy_download
        ) as download_spy:
            render_clip(clip.id)

        download_spy.assert_called_once()
        assert captured_results and captured_results[0] is not None, "B-roll download failed"

        db_session.refresh(clip)
        assert clip.status == ClipStatus.ready
        output_path = Path(clip.video_file_path)
        assert output_path.is_file()
        assert output_path.stat().st_size > 0
