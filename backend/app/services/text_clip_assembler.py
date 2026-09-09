"""Text-to-clip assembler: builds a 9:16 MP4 from B-roll footage + voiceover + captions.

Builds a complete, story-driven Short (~25–35 seconds) from a text-sourced Clip:
1. Synthesizes high-quality voiceover audio (via edge-tts / OpenAI / say)
   and captures sentence/phrase timestamps.
2. Sources multiple vertical HD B-roll clips matching each scene keyword.
3. Normalizes and loops each B-roll video to its scene duration, stitching them
   into a dynamic multi-scene visual progression.
4. Generates timed, word-highlighted subtitle overlays (Hormozi / Neon / etc.)
   using Pillow.
5. Composites the visual scenes, voiceover audio track, and animated captions
   into a ready-to-publish 1080x1920 vertical MP4.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import textwrap
import uuid
from pathlib import Path

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.clip import Clip, ClipStatus
from app.models.video_project import VideoProject, VideoProjectStatus
from app.services.caption_render import render_caption_images
from app.services.video_render import _caption_font_file
from app.services.voice_synthesis import synthesize_speech_sync

logger = logging.getLogger(__name__)

_RENDER_W = 1080
_RENDER_H = 1920
_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ---------------------------------------------------------------------------
# Public entry-point (called by task_queue)
# ---------------------------------------------------------------------------

def assemble_text_clip(clip_id: int) -> None:
    """Build a 9:16 MP4 for a text-sourced clip and mark it ready."""
    db = SessionLocal()
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if clip is None:
            logger.error("assemble_text_clip: clip_id=%s not found", clip_id)
            return

        clip.status = ClipStatus.rendering
        db.commit()

        output_path = _assemble(clip, db)

        clip.video_file_path = str(output_path)
        thumb = _extract_thumbnail(output_path, float(clip.end_time - clip.start_time))
        if thumb:
            clip.thumbnail_path = str(thumb)
        clip.status = ClipStatus.ready
        db.commit()
        logger.info("Text clip assembled successfully: clip_id=%s -> %s", clip_id, output_path)

        _update_parent_project_status(clip.video_project_id, db)

    except Exception as exc:
        logger.exception("assemble_text_clip failed for clip_id=%s", clip_id)
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if clip:
                clip.status = ClipStatus.failed
                clip.virality_reason = f"Assembly failed: {exc}"
                db.commit()
                _update_parent_project_status(clip.video_project_id, db)
        except Exception:
            logger.exception("Could not mark clip_id=%s as failed", clip_id)
    finally:
        db.close()


def _update_parent_project_status(project_id: int, db) -> None:
    """If all clips for this project are in a terminal state, set the project status."""
    try:
        clips = db.query(Clip).filter(Clip.video_project_id == project_id).all()
        if not clips:
            return
        all_terminal = all(c.status in (ClipStatus.ready, ClipStatus.failed) for c in clips)
        if all_terminal:
            project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
            if project and project.status == VideoProjectStatus.generating:
                if any(c.status == ClipStatus.ready for c in clips):
                    project.status = VideoProjectStatus.ready
                else:
                    project.status = VideoProjectStatus.failed
                    project.error_message = "All generated clips failed to render"
                db.commit()
                logger.info("Updated parent project %s status to %s", project_id, project.status)
    except Exception:
        logger.exception("Failed to update parent project status for project_id=%s", project_id)


# ---------------------------------------------------------------------------
# Core assembly pipeline
# ---------------------------------------------------------------------------

def _assemble(clip: Clip, db) -> Path:  # type: ignore[no-untyped-def]
    """Build multi-scene B-roll video + voiceover audio + timed captions."""
    narration = clip.caption_text or clip.title
    keywords = _extract_keywords_from_clip(clip)

    with tempfile.TemporaryDirectory(prefix=f"vts_text_clip_{clip.id}_") as tmp_dir:
        tmp = Path(tmp_dir)

        # 1. Synthesize Voiceover Audio
        voice_path = tmp / "narration.mp3"
        logger.info("Synthesizing speech for clip_id=%s...", clip.id)
        _, events, voice_duration = synthesize_speech_sync(narration, voice_path)

        total_duration = max(15.0, voice_duration)
        logger.info("Voiceover ready: duration=%.2fs (%d timed caption events)", total_duration, len(events))

        # Update clip end time to match the real voice narration duration
        clip.start_time = 0.0
        clip.end_time = round(total_duration, 2)
        db.commit()

        # 2. Sourcing B-Roll footage for each scene
        scene_count = max(len(keywords), 3)
        urls = _fetch_stock_urls(keywords, target_count=scene_count)

        # Download raw videos
        downloaded_raw = _download_clips(urls, str(tmp))
        if not downloaded_raw:
            logger.warning("No B-roll videos downloaded for clip_id=%s; generating animated background scenes", clip.id)
            downloaded_raw = _generate_procedural_scenes(keywords, str(tmp))

        # 3. Normalize each scene with loop and exact duration
        scene_duration = total_duration / len(downloaded_raw)
        normalized_scenes: list[Path] = []

        for i, raw_video in enumerate(downloaded_raw):
            norm_path = tmp / f"scene_{i:03d}.mp4"
            _normalize_scene(raw_video, norm_path, scene_duration)
            normalized_scenes.append(norm_path)

        # 4. Concatenate normalized scenes into base video
        concat_file = tmp / "concat.txt"
        concat_file.write_text("\n".join([f"file '{p.as_posix()}'" for p in normalized_scenes]) + "\n")

        base_video = tmp / "base_video.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                str(base_video),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )

        # 5. Render timed caption overlays
        font_file = _caption_font_file()
        style_name = clip.caption_style.value if hasattr(clip.caption_style, "value") else str(clip.caption_style or "hormozi")
        captions_dir = tmp / "captions"
        captions_dir.mkdir(parents=True, exist_ok=True)
        caption_images = render_caption_images(
            events,
            captions_dir,
            _RENDER_W,
            _RENDER_H,
            font_file,
            style_name,
        )

        # 6. Composite Base Video + Voiceover Audio + Captions
        composed_output = tmp / "final_composed.mp4"
        _composite_video(
            base_video=base_video,
            voice_path=voice_path,
            caption_images=caption_images,
            output_path=composed_output,
            duration=total_duration,
        )

        # Move to permanent uploads dir
        return _persist_output(composed_output, clip.id)


def _normalize_scene(input_path: Path, output_path: Path, duration: float) -> None:
    """Normalize a B-roll video to 1080x1920 30fps and loop to exact `duration`."""
    scale_filter = (
        f"scale={_RENDER_W}:{_RENDER_H}:force_original_aspect_ratio=increase,"
        f"crop={_RENDER_W}:{_RENDER_H},"
        f"setsar=1,fps=30"
    )

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(input_path),
        "-t", f"{duration:.3f}",
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        logger.error("Scene normalization failed for %s: %s", input_path, res.stderr[-1000:])
        raise RuntimeError(f"Scene normalization failed: {res.stderr[-500:]}")


def _composite_video(
    *,
    base_video: Path,
    voice_path: Path,
    caption_images: list | None,
    output_path: Path,
    duration: float,
) -> None:
    """Combine base video, voice audio track, and timed caption overlays into final MP4."""
    cmd = ["ffmpeg", "-y", "-i", str(base_video), "-i", str(voice_path)]

    if caption_images:
        filter_parts = []
        last_stream = "0:v"

        for idx, img in enumerate(caption_images):
            cmd.extend(["-i", str(img.path)])
            input_idx = idx + 2
            out_stream = f"cap_{idx}"
            # Overlay only during [img.start, img.end]
            filter_parts.append(
                f"[{last_stream}][{input_idx}:v]overlay=0:{img.y}:enable='between(t,{img.start:.3f},{img.end:.3f})'[{out_stream}]"
            )
            last_stream = out_stream

        filter_complex_str = ";".join(filter_parts)
        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", f"[{last_stream}]",
            "-map", "1:a",
        ])
    else:
        cmd.extend(["-map", "0:v", "-map", "1:a"])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{duration:.3f}",
        "-movflags", "+faststart",
        str(output_path),
    ])

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if res.returncode != 0:
        logger.error("Final compositing failed: %s", res.stderr[-2000:])
        raise RuntimeError(f"ffmpeg composition failed: {res.stderr[-500:]}")


def _extract_keywords_from_clip(clip: Clip) -> list[str]:
    """Get the scene keywords stored on the clip."""
    try:
        if clip.virality_reason and clip.virality_reason.startswith("{"):
            data = json.loads(clip.virality_reason)
            kws = data.get("keywords", [])
            if kws:
                return kws
    except Exception:
        pass

    text = f"{clip.title} {clip.caption_text or ''}"
    from app.services.broll_sourcing import extract_keywords
    return extract_keywords(text, max_keywords=4)


def _fetch_stock_urls(keywords: list[str], target_count: int) -> list[str]:
    """Fetch downloadable vertical video URLs for each scene keyword."""
    async def _run() -> list[str]:
        from app.services.broll_sourcing import search_pexels, search_pixabay

        urls: list[str] = []
        seen: set[str] = set()

        for keyword in keywords:
            results = await search_pexels(keyword, per_page=3)
            if not results and getattr(settings, "PIXABAY_API_KEY", ""):
                results = await search_pixabay(keyword, per_page=3)

            for r in results:
                url = r.get("asset_url")
                if url and url not in seen:
                    seen.add(url)
                    urls.append(url)
                    break  # One best video per scene keyword

            if len(urls) >= target_count:
                break

        return urls

    return asyncio.run(_run())


def _download_clips(urls: list[str], tmp_dir: str) -> list[Path]:
    """Download each URL into tmp_dir, return successfully downloaded paths."""
    downloaded: list[Path] = []
    for i, url in enumerate(urls):
        dest = Path(tmp_dir) / f"broll_{i:03d}.mp4"
        try:
            with httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=65536):
                            f.write(chunk)
            downloaded.append(dest)
            logger.debug("Downloaded B-roll %s -> %s", url, dest)
        except Exception as exc:
            logger.warning("Failed to download B-roll %s: %s", url, exc)

    return downloaded


def _generate_procedural_scenes(keywords: list[str], tmp_dir: str) -> list[Path]:
    """Generate subtle animated gradient scenes as fallback when no internet/stock video found."""
    scenes: list[Path] = []
    colors = ["0x0d1b2a", "0x1b263b", "0x415a77", "0x111d4a"]

    for i in range(max(len(keywords), 3)):
        c = colors[i % len(colors)]
        scene_path = Path(tmp_dir) / f"proc_{i:03d}.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"color=c={c}:s={_RENDER_W}x{_RENDER_H}:d=10",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                str(scene_path),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        scenes.append(scene_path)

    return scenes


def _persist_output(tmp_path: Path, clip_id: int) -> Path:
    """Move the rendered MP4 from the temp dir to the permanent uploads directory."""
    out_dir = _uploads_dir()
    final_name = f"text_clip_{clip_id}_{uuid.uuid4().hex[:8]}.mp4"
    final_path = out_dir / final_name
    shutil.move(str(tmp_path), str(final_path))
    return final_path


def _uploads_dir() -> Path:
    """Return (and create if needed) the uploads directory."""
    upload_root = Path(getattr(settings, "UPLOAD_ROOT", "./uploads"))
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root


def _extract_thumbnail(video_path: Path, duration: float) -> Path | None:
    """Grab a poster frame from the rendered clip."""
    thumbnail_path = video_path.with_suffix(".jpg")
    timestamp = min(1.0, max(0.0, duration / 2))
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", f"{timestamp:.2f}",
                "-i", str(video_path),
                "-vframes", "1", "-q:v", "2",
                str(thumbnail_path),
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
        if thumbnail_path.is_file() and thumbnail_path.stat().st_size > 0:
            return thumbnail_path
    except Exception as exc:
        logger.warning("Could not extract thumbnail for %s: %s", video_path, exc)
    return None
