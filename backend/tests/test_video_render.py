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
from app.models.transcript_segment import TranscriptSegment
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


def _probe_stream(path: Path, stream: str, entries: str) -> dict[str, str]:
    """Return the requested ffprobe stream entries as a dict."""

    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            stream,
            "-show_entries",
            f"stream={entries}",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return dict(
        line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line
    )


def _make_wide_source_video(path: Path, duration: float = 3.0) -> None:
    """Synthesize a 16:9 source with real picture detail (not a flat colour),
    so framing behaviour is actually observable in the output."""

    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=s=1920x1080:r=30:d={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=f=440:d={duration}",
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


def _mean_top_strip_rgb(path: Path) -> tuple[int, int, int]:
    """Average colour of the top 200px of the first frame.

    With a 16:9 source on a 9:16 canvas that band is either the blurred
    fill or a black bar, which is exactly the difference under test.
    """

    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            "crop=1080:200:0:0,scale=1:1",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    pixel = result.stdout[:3]
    return (pixel[0], pixel[1], pixel[2])


def _brightest_pixel_in_caption_band(path: Path) -> int:
    """Brightest pixel in the lower third of the first frame.

    A burned-in caption is white on black; over the dark synthetic source
    used here, its presence or absence is the difference between a bright
    pixel and none at all.
    """

    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            "0.5",
            "-i",
            str(path),
            "-vf",
            "crop=1080:640:0:1100,scale=64:64",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    return max(result.stdout) if result.stdout else 0


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

    def test_render_matches_youtube_shorts_upload_spec(
        self, db_session: Session, test_user: User
    ) -> None:
        """The exported MP4 must be directly uploadable to YouTube Shorts:
        1080x1920 @ 30fps, H.264 High/yuv420p, 48kHz stereo AAC, and
        faststart (moov atom ahead of mdat) so it streams while loading."""

        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / "spec_source.mp4"
        _make_test_source_video(source_file, duration=4.0)

        project = VideoProject(
            user_id=test_user.id,
            title="Spec project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/spec_source.mp4",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Spec clip",
            start_time=0.0,
            end_time=3.0,
            order_index=0,
            status=ClipStatus.rendering,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        render_clip(clip.id)

        db_session.refresh(clip)
        assert clip.status == ClipStatus.ready
        output_path = Path(clip.video_file_path)

        video = _probe_stream(output_path, "v:0", "width,height,r_frame_rate,pix_fmt,profile")
        assert (video["width"], video["height"]) == ("1080", "1920")
        assert video["r_frame_rate"] == "30/1"
        assert video["pix_fmt"] == "yuv420p"
        assert video["profile"] == "High"

        audio = _probe_stream(output_path, "a:0", "codec_name,sample_rate,channels")
        assert audio["codec_name"] == "aac"
        assert audio["sample_rate"] == "48000"
        assert audio["channels"] == "2"

        head = output_path.read_bytes()[:4096]
        assert b"moov" in head, "moov atom is not at the front (+faststart missing)"

    def test_render_writes_a_poster_thumbnail(
        self, db_session: Session, test_user: User
    ) -> None:
        """A poster frame is written next to the MP4 and recorded on the
        clip, so the library grid (and a YouTube custom thumbnail) has
        something real to show."""

        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / "thumb_source.mp4"
        _make_test_source_video(source_file, duration=3.0)

        project = VideoProject(
            user_id=test_user.id,
            title="Thumb project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/thumb_source.mp4",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Thumb clip",
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
        assert clip.thumbnail_path, "no thumbnail recorded on the clip"
        thumbnail = Path(clip.thumbnail_path)
        assert thumbnail.is_file()
        assert thumbnail.stat().st_size > 0


class TestFfmpegCapabilityProbe:
    """`_available_filters` gates blur framing, loudness normalisation and
    caption burn-in. When its parsing breaks, renders keep succeeding but
    silently drop all three -- so the parse itself needs a test."""

    def test_parses_the_installed_ffmpeg_filter_table(self) -> None:
        from app.services.video_render import _available_filters

        _available_filters.cache_clear()
        filters = _available_filters()

        # Filters every ffmpeg build has. The flags column is 2 chars wide
        # on some versions and 3 on others -- both must parse.
        assert {"scale", "overlay", "crop", "format", "split"} <= filters
        assert "=" not in filters, "legend lines were parsed as filter names"


class TestSplitScreenFraming:
    """`_frame_9x16` under RENDER_FRAMING=auto, with the analysis stubbed:
    what matters here is the filter graph it builds, not the detection
    (covered against real footage in test_reframe.py)."""

    @staticmethod
    def _framing(with_split: bool):  # type: ignore[no-untyped-def]
        from app.services.reframe import (
            SpeakerFraming,
            SpeakerWindow,
            SplitFraming,
            SplitSection,
        )

        split = (
            SplitFraming(
                pane_count=2,
                crop_width=1102,
                crop_height=980,
                sections=(
                    SplitSection(
                        start_time=0.0,
                        end_time=8.0,
                        panes=(
                            SpeakerWindow(0.0, 0, 80),
                            SpeakerWindow(0.0, 818, 4),
                        ),
                    ),
                ),
            )
            if with_split
            else None
        )
        return SpeakerFraming(
            source_width=1920,
            source_height=1080,
            crop_width=608,
            crop_height=1080,
            windows=(SpeakerWindow(0.0, 152, 0),),
            split=split,
        )

    def _graph(self, with_split: bool) -> str:
        import ffmpeg

        from app.services import video_render as video_render_module

        with patch.object(
            video_render_module,
            "compute_speaker_framing",
            return_value=self._framing(with_split),
        ):
            stream = video_render_module._frame_9x16(
                ffmpeg.input("source.mp4"),
                source_path="source.mp4",
                start_time=0.0,
                duration=20.0,
            )
        return " ".join(
            ffmpeg.compile(ffmpeg.output(stream, "out.mp4"), overwrite_output=True)
        )

    def test_two_speakers_are_stacked_over_the_single_speaker_frame(self) -> None:
        graph = self._graph(with_split=True)

        # One crop per pane, stacked, and shown only for the stretch the
        # analysis found -- the rest of the clip keeps the single crop.
        assert "vstack" in graph
        assert "crop=1102:980" in graph, "panes are cropped at the split's own size"
        # Shown for exactly the stretch the analysis found (the comma is
        # escaped for the filtergraph), so the clip cuts back to a single
        # speaker afterwards.
        assert r"overlay=enable=between(t\,0.00\,8.00)" in graph
        assert "crop=608:1080" in graph, "the single-speaker frame is still there"

    def test_a_clip_with_one_speaker_is_not_stacked(self) -> None:
        graph = self._graph(with_split=False)

        assert "vstack" not in graph
        assert "crop=608:1080" in graph


class TestFraming:
    def test_blur_framing_fills_the_frame_instead_of_black_bars(
        self, db_session: Session, test_user: User, tmp_path: Path
    ) -> None:
        """A 16:9 broadcast source on a 9:16 canvas must get the blurred
        fill, not two thirds of the frame in black bars."""

        if "gblur" not in video_render_module._available_filters():
            pytest.skip("ffmpeg build has no gblur filter")

        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / "wide_source.mp4"
        _make_wide_source_video(source_file)

        project = VideoProject(
            user_id=test_user.id,
            title="Wide project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path="videos/wide_source.mp4",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Wide clip",
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
        red, green, blue = _mean_top_strip_rgb(Path(clip.video_file_path))
        assert max(red, green, blue) > 12, (
            "the top of the frame is black -- the blurred fill did not apply"
        )


class TestBurnedInCaptions:
    """Captions must survive whatever the local ffmpeg was built with.

    `ass`/`subtitles` needs libass and `drawtext` needs libfreetype; both
    are optional at compile time, and when they were the only options a
    build without them produced a silently uncaptioned Short.
    """

    def _project_with_transcript(
        self, db_session: Session, test_user: User, source_name: str
    ) -> VideoProject:
        import app.services.storage as storage_module

        source_file = storage_module.UPLOAD_ROOT / "videos" / source_name
        _make_test_source_video(source_file, duration=4.0)

        project = VideoProject(
            user_id=test_user.id,
            title="Captioned project",
            source_type=SourceType.upload,
            status=VideoProjectStatus.ready,
            source_file_path=f"videos/{source_name}",
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    def test_transcript_is_burned_into_the_exported_frames(
        self, db_session: Session, test_user: User
    ) -> None:
        project = self._project_with_transcript(
            db_session, test_user, "captioned_source.mp4"
        )
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=0.0,
                end_time=3.0,
                text="Subtitles must appear",
                is_highlight=True,
            )
        )
        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Captioned clip",
            start_time=0.0,
            end_time=3.0,
            order_index=0,
            status=ClipStatus.rendering,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        render_clip(clip.id)

        db_session.refresh(clip)
        assert clip.status == ClipStatus.ready
        assert _brightest_pixel_in_caption_band(Path(clip.video_file_path)) > 180, (
            "no burned-in caption found in the lower third of the frame"
        )

    def test_a_clip_with_nothing_to_say_renders_clean(
        self, db_session: Session, test_user: User
    ) -> None:
        """The counterpart to the test above: with no transcript and no
        caption_text there must be no text band, so the assertion above is
        actually detecting captions rather than the source footage."""

        project = self._project_with_transcript(
            db_session, test_user, "uncaptioned_source.mp4"
        )
        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Silent clip",
            start_time=0.0,
            end_time=3.0,
            order_index=0,
            status=ClipStatus.rendering,
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        render_clip(clip.id)

        db_session.refresh(clip)
        assert clip.status == ClipStatus.ready
        assert _brightest_pixel_in_caption_band(Path(clip.video_file_path)) < 120

    def test_caption_text_overrides_the_transcript(
        self, db_session: Session, test_user: User
    ) -> None:
        project = self._project_with_transcript(
            db_session, test_user, "override_source.mp4"
        )
        db_session.add(
            TranscriptSegment(
                video_project_id=project.id,
                start_time=0.0,
                end_time=3.0,
                text="The raw transcript",
                is_highlight=True,
            )
        )
        clip = Clip(
            video_project_id=project.id,
            user_id=test_user.id,
            title="Override clip",
            start_time=0.0,
            end_time=3.0,
            order_index=0,
            status=ClipStatus.rendering,
            caption_text="My own hook line",
        )
        db_session.add(clip)
        db_session.commit()
        db_session.refresh(clip)

        render_clip(clip.id)

        db_session.refresh(clip)
        assert clip.status == ClipStatus.ready
        assert _brightest_pixel_in_caption_band(Path(clip.video_file_path)) > 180
