"""Copyright-Safe & Fair-Use Transformative Rendering Service.

Transforms a raw highlight clip from a third-party long-form video into a
Fair-Use compliant, Content-ID resistant 9:16 YouTube Short by:

1. **Hook Trimming (< 7.5s)**: Caps the continuous raw source clip to just the
   opening hook sentence (default max 7.5 seconds) so uninterrupted source
   audio/video never exceeds typical Content ID match windows.
2. **Audio & Visual Fingerprint Protection on the Hook**: Applies subtle
   spectral/tempo micro-adjustment (`asetrate` + `aresample` + `atempo` +
   bandpass EQ) and visual micro-zoom/color-grade transformation on the hook
   so automated frame and audio hashes are disrupted while speech stays clear.
3. **Original AI Transformative Commentary & Critique**: Generates a spoken
   analytical breakdown/reaction script responding directly to the clip's
   claims and synthesizes a studio voiceover track (via `voice_synthesis`).
4. **100% Full-Screen B-Roll Cutaways During Commentary**: Replaces both the
   original audio and original video stream after the hook with full-screen
   9:16 B-roll scenes and synchronized captions so >70% of the exported Short
   is original transformative audio-visual work.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ffmpeg

from app.config import settings
from app.services.broll_sourcing import _synthesize_local_broll, extract_keywords
from app.services.text_generation import _extract_json_payload, _resolve_llm_credentials
from app.services.voice_synthesis import synthesize_speech_sync

if TYPE_CHECKING:
    from app.models.broll_asset import BrollAsset
    from app.models.clip import BrollPlacement, ClipCaptionStyle
    from app.models.transcript_segment import TranscriptSegment
    from app.services.reframe import SpeakerFraming

logger = logging.getLogger(__name__)

# Maximum seconds of original source footage/audio retained as the opening hook
DEFAULT_MAX_HOOK_SECONDS = 7.5
MIN_HOOK_SECONDS = 2.0


def compute_hook_duration(
    clip_start: float,
    clip_duration: float,
    transcript_segments: list[TranscriptSegment],
    max_hook_seconds: float | None = None,
) -> float:
    """Compute a clean sentence-bounded hook duration capped at `max_hook_seconds`.

    Keeps only the opening hook of the third-party video (typically 4-7.5s)
    rather than 35-50s of uninterrupted source audio.
    """
    cap = max_hook_seconds or getattr(
        settings, "RENDER_HOOK_MAX_SECONDS", DEFAULT_MAX_HOOK_SECONDS
    )
    if clip_duration <= 0:
        return MIN_HOOK_SECONDS

    # For very short clips (e.g. 2-6s in unit tests), keep ~55% as hook
    if clip_duration <= cap:
        return round(
            max(min(clip_duration * 0.55, cap), min(clip_duration, MIN_HOOK_SECONDS)),
            2,
        )

    clip_end = clip_start + clip_duration
    in_window = [
        seg
        for seg in sorted(transcript_segments, key=lambda s: s.start_time)
        if seg.end_time > clip_start and seg.start_time < clip_end
    ]

    for seg in in_window:
        rel_end = seg.end_time - clip_start
        if MIN_HOOK_SECONDS <= rel_end <= cap:
            text = (seg.text or "").strip()
            if text.endswith((".", "!", "?")) or rel_end >= 4.0:
                return round(rel_end, 2)

    return round(min(cap, clip_duration), 2)


def generate_transformative_commentary(
    clip_title: str,
    transcript_text: str,
    hook_text: str = "",
) -> str:
    """Generate an original analytical commentary/reaction script for Fair Use.

    Uses OpenRouter/OpenAI when configured and falls back to a deterministic
    editorial breakdown engine offline or in zero-key environments.
    """
    clean_transcript = " ".join((transcript_text or clip_title).split()).strip()
    clean_title = " ".join((clip_title or "this clip").split()).strip(" .,-")

    creds = _resolve_llm_credentials()
    if creds is not None:
        api_key, base_url, model = creds
        try:
            script = _llm_generate_commentary(
                clean_title, clean_transcript, hook_text, api_key, base_url, model
            )
            if script and len(script.split()) >= 15:
                return script
        except Exception as exc:
            logger.warning(
                "LLM commentary generation failed (%s); using local transformative engine",
                exc,
            )

    return _heuristic_transformative_commentary(clean_title, clean_transcript)


def _llm_generate_commentary(
    title: str,
    transcript_text: str,
    hook_text: str,
    api_key: str,
    base_url: str | None,
    model: str,
) -> str:
    """Call OpenRouter/OpenAI to write a punchy 35-50 word transformative reaction."""
    import openai

    client = (
        openai.OpenAI(api_key=api_key, base_url=base_url, timeout=8.0)
        if base_url
        else openai.OpenAI(api_key=api_key, timeout=8.0)
    )
    prompt = (
        "Write a 35 to 50 word transformative commentary and critical breakdown reacting "
        "to the following video hook for a YouTube Short (Fair Use analysis/parody style). "
        "Do NOT repeat the quote verbatim; analyze why this claim matters, what most people "
        "miss, and the real-world takeaway.\n\n"
        f"Clip Title: {title}\n"
        f"Opening Hook: {hook_text or title}\n"
        f"Full Context: {transcript_text[:500]}\n\n"
        'Return ONLY JSON: {"commentary": "your spoken commentary script"}'
    )
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=200,
    )
    raw = _extract_json_payload(response.choices[0].message.content or "{}")
    data = json.loads(raw)
    if isinstance(data, dict) and data.get("commentary"):
        return str(data["commentary"]).strip()
    return ""


def _heuristic_transformative_commentary(title: str, transcript_text: str) -> str:
    """Build a context-specific analytical commentary script without external APIs."""
    keywords = extract_keywords(f"{title} {transcript_text}", max_keywords=3)
    primary_topic = keywords[0] if keywords else "technology"
    secondary_topic = keywords[1] if len(keywords) > 1 else "innovation"

    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", transcript_text)
        if len(s.strip().split()) >= 4
    ]
    key_point = sentences[-1] if len(sentences) > 1 else title
    key_words = " ".join(key_point.split()[:10]).strip(" .,!?;:")

    return (
        f"Hold on, let's break down what that statement about {primary_topic} actually means. "
        f"When they mention {key_words}, most people overlook the deeper shift happening in "
        f"{secondary_topic}. Instead of taking the hype at face value, the real takeaway is how "
        f"fast this changes everyday decisions. Drop your thoughts in the comments!"
    )


def ensure_full_screen_broll_scenes(
    broll_paths: list[Path],
    keywords: list[str],
    commentary_duration: float,
    tmp_dir: Path,
    width: int,
    height: int,
    fps: int,
) -> Path:
    """Build a normalized 9:16 full-screen B-roll video stream covering `commentary_duration`.

    Uses attached B-roll files first; if none are available, synthesizes visual
    B-roll cutaway cards or gradient motion scenes so the commentary section
    never falls back to raw unedited source footage.
    """
    usable_paths = [p for p in broll_paths if p is not None and p.is_file()]

    if not usable_paths:
        fallback_kws = keywords or ["analysis", "insight", "breakdown"]
        for idx, kw in enumerate(fallback_kws[:3]):
            synthesized = _synthesize_local_broll(
                kw,
                idx,
                max(3.5, commentary_duration / max(len(fallback_kws[:3]), 1)),
            )
            if synthesized and synthesized.get("asset_url"):
                from app.services.storage import UPLOAD_ROOT

                candidate = UPLOAD_ROOT / str(synthesized["asset_url"])
                if candidate.is_file():
                    usable_paths.append(candidate)

    if not usable_paths:
        proc_path = tmp_dir / "fallback_broll_scene.mp4"
        dur_str = f"{max(commentary_duration, 1.0):.3f}"
        color_src = f"color=c=0x111d4a:s={width}x{height}:r={fps}:d={dur_str}"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                color_src,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(proc_path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
        )
        usable_paths.append(proc_path)

    scene_dur = max(0.5, commentary_duration / len(usable_paths))
    normalized_scenes: list[Path] = []
    scale_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}:(iw-{width})/2:(ih-{height})/2,"
        f"setsar=1,fps={fps},format=yuv420p"
    )

    for i, src_path in enumerate(usable_paths):
        scene_out = tmp_dir / f"cs_broll_norm_{i:03d}.mp4"
        is_img = src_path.suffix.lower() in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".bmp",
            ".gif",
        }
        cmd = ["ffmpeg", "-y"]
        if is_img:
            cmd.extend(["-loop", "1", "-i", str(src_path), "-t", f"{scene_dur:.3f}"])
        else:
            cmd.extend(
                ["-stream_loop", "-1", "-i", str(src_path), "-t", f"{scene_dur:.3f}"]
            )
        cmd.extend(
            [
                "-vf",
                scale_filter,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(scene_out),
            ]
        )
        subprocess.run(
            cmd,
            check=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
        )
        normalized_scenes.append(scene_out)

    if len(normalized_scenes) == 1:
        return normalized_scenes[0]

    concat_list = tmp_dir / "cs_broll_concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in normalized_scenes) + "\n",
        encoding="utf-8",
    )
    stitched = tmp_dir / "cs_broll_stitched.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-t",
            f"{commentary_duration:.3f}",
            "-c",
            "copy",
            str(stitched),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=120,
    )
    return stitched


def render_copyright_safe_clip(
    *,
    source_path: str,
    start_time: float,
    duration: float,
    clip_title: str,
    caption_text: str | None,
    transcript_segments: list[TranscriptSegment],
    broll_assets: list[BrollAsset],
    output_path: Path,
    tmp_dir: Path,
    framing: str | None = None,
    caption_style: ClipCaptionStyle | None = None,
    broll_placement: BrollPlacement | None = None,
) -> SpeakerFraming | None:
    """Render a clip in Copyright-Safe / Fair-Use Transformative mode.

    1. Trims original footage & audio to the opening hook (<= 7.5s).
    2. Applies subtle visual & audio fingerprint protection on the hook.
    3. Synthesizes original AI commentary voiceover + full-screen 9:16 B-roll
       cutaways for the remainder of the Short.
    4. Burns unified word-synced captions across both phases and encodes to
       YouTube Shorts upload spec.
    """
    from app.models.clip import BrollPlacement as BrollPlacementEnum
    from app.services.video_render import (
        _apply_broll,
        _apply_captions,
        _audio_output_kwargs,
        _available_filters,
        _caption_events,
        _frame_9x16,
        _has_audio_stream,
        _resolve_broll_path,
        _video_output_kwargs,
    )

    width = settings.RENDER_WIDTH
    height = settings.RENDER_HEIGHT
    fps = settings.RENDER_FPS
    placement = broll_placement or BrollPlacementEnum.bottom

    # 1. Compute trimmed hook duration (<= 7.5s)
    hook_duration = compute_hook_duration(
        start_time, duration, transcript_segments
    )

    # Extract full transcript text and hook text for commentary generation
    clip_end = start_time + duration
    window_segs = [
        s
        for s in sorted(transcript_segments, key=lambda seg: seg.start_time)
        if s.end_time > start_time and s.start_time < clip_end
    ]
    full_transcript_text = (
        " ".join((s.text or "").strip() for s in window_segs if (s.text or "").strip())
        or caption_text
        or clip_title
    )
    hook_segs = [
        s for s in window_segs if s.start_time < start_time + hook_duration
    ]
    hook_text = (
        " ".join((s.text or "").strip() for s in hook_segs if (s.text or "").strip())
        or full_transcript_text[:140]
    )

    # 2. Generate transformative commentary script & synthesize voiceover
    commentary_script = generate_transformative_commentary(
        clip_title=clip_title,
        transcript_text=full_transcript_text,
        hook_text=hook_text,
    )
    raw_voice_path = tmp_dir / "commentary_voice.mp3"
    _, commentary_events, raw_voice_dur = synthesize_speech_sync(
        commentary_script, raw_voice_path
    )
    commentary_duration = max(3.5, round(raw_voice_dur, 2))

    # 3. Render Hook Video (0 -> hook_duration) with visual fingerprint transform
    hook_input = ffmpeg.input(source_path, ss=start_time, t=hook_duration)
    hook_stream, speaker_framing = _frame_9x16(
        hook_input,
        source_path=source_path,
        start_time=start_time,
        duration=hook_duration,
        framing=framing,
    )
    hook_stream = hook_stream.filter("fps", fps=fps)

    # Visual fingerprint protection: subtle 1.04x zoom-crop + color shift + optional mirror
    zoom_w = int(width * 1.04) & ~1
    zoom_h = int(height * 1.04) & ~1
    hook_stream = (
        hook_stream.filter("scale", zoom_w, zoom_h)
        .filter("crop", width, height, (zoom_w - width) // 2, (zoom_h - height) // 2)
        .filter("eq", contrast=1.04, brightness=0.015, saturation=1.08)
        .filter("setsar", 1)
    )
    if getattr(settings, "RENDER_MIRROR_HOOK", False):
        hook_stream = hook_stream.filter("hflip")

    # Apply any B-roll overlays that fall inside the hook window
    hook_stream = _apply_broll(
        hook_stream, broll_assets, hook_duration, tmp_dir, placement
    )

    hook_video_path = tmp_dir / "cs_hook_video.mp4"
    (
        ffmpeg.output(
            hook_stream,
            str(hook_video_path),
            vcodec="libx264",
            preset="ultrafast",
            pix_fmt="yuv420p",
            r=fps,
            an=None,
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )

    # 4. Build Full-Screen B-Roll Cutaway Video for Commentary Phase
    resolved_brolls: list[Path] = []
    for asset in broll_assets:
        resolved = _resolve_broll_path(asset.asset_url, tmp_dir)
        if resolved is not None:
            resolved_brolls.append(resolved)

    keywords = [a.keyword for a in broll_assets if a.keyword] or extract_keywords(
        f"{clip_title} {full_transcript_text}", max_keywords=3
    )
    commentary_video_path = ensure_full_screen_broll_scenes(
        broll_paths=resolved_brolls,
        keywords=keywords,
        commentary_duration=commentary_duration,
        tmp_dir=tmp_dir,
        width=width,
        height=height,
        fps=fps,
    )

    # 5. Prepare Hook Audio (with spectral/tempo fingerprint protection) + Commentary Audio
    hook_audio_path = tmp_dir / "cs_hook_audio.wav"
    if _has_audio_stream(source_path):
        # Subtle pitch/tempo micro-shift (2.5%) + bandpass filter breaks Content ID audio match
        audio_af = (
            "asetrate=48000*1.025,aresample=48000,atempo=0.9756,"
            "highpass=f=75,lowpass=f=14500"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start_time:.3f}",
                "-t",
                f"{hook_duration:.3f}",
                "-i",
                source_path,
                "-af",
                audio_af,
                "-ar",
                "48000",
                "-ac",
                "2",
                str(hook_audio_path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=60,
        )
    else:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r=48000:cl=stereo:d={hook_duration:.3f}",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(hook_audio_path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )

    commentary_audio_path = tmp_dir / "cs_commentary_audio.wav"
    voice_res = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_voice_path),
            "-t",
            f"{commentary_duration:.3f}",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(commentary_audio_path),
        ],
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )
    if (
        voice_res.returncode != 0
        or not commentary_audio_path.is_file()
        or commentary_audio_path.stat().st_size < 500
    ):
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r=48000:cl=stereo:d={commentary_duration:.3f}",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(commentary_audio_path),
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
        )

    # Concatenate hook + commentary video and audio streams
    v_concat = tmp_dir / "cs_v_concat.txt"
    v_concat.write_text(
        f"file '{hook_video_path.as_posix()}'\nfile '{commentary_video_path.as_posix()}'\n",
        encoding="utf-8",
    )
    stitched_video_path = tmp_dir / "cs_stitched_video.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(v_concat),
            "-c",
            "copy",
            str(stitched_video_path),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=120,
    )

    a_concat = tmp_dir / "cs_a_concat.txt"
    a_concat.write_text(
        f"file '{hook_audio_path.as_posix()}'\nfile '{commentary_audio_path.as_posix()}'\n",
        encoding="utf-8",
    )
    stitched_audio_path = tmp_dir / "cs_stitched_audio.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(a_concat),
            "-c",
            "copy",
            str(stitched_audio_path),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=60,
    )

    # 6. Build unified caption timeline (Hook captions + Commentary captions)
    total_duration = hook_duration + commentary_duration
    hook_captions = _caption_events(
        caption_text=caption_text if not window_segs else None,
        transcript_segments=transcript_segments,
        clip_start=start_time,
        duration=hook_duration,
    )
    shifted_commentary_captions = [
        (
            round(hook_duration + ev_start, 2),
            round(min(total_duration, hook_duration + ev_end), 2),
            ev_text,
        )
        for ev_start, ev_end, ev_text in commentary_events
        if ev_end > ev_start
    ]
    combined_captions = [*hook_captions, *shifted_commentary_captions]

    # 7. Burn in unified captions and encode to YouTube Shorts upload spec
    final_v_in = ffmpeg.input(str(stitched_video_path))
    final_a_in = ffmpeg.input(str(stitched_audio_path))

    captioned_v: Any = _apply_captions(
        final_v_in.video,
        combined_captions,
        tmp_dir,
        caption_style,
        broll_placement=placement,
        has_broll=False,
    )

    audio_out = final_a_in.audio
    if "loudnorm" in _available_filters():
        audio_out = audio_out.filter(
            "loudnorm", i=settings.RENDER_AUDIO_LUFS, tp=-1.5, lra=11
        )

    (
        ffmpeg.output(
            captioned_v,
            audio_out,
            str(output_path),
            **_video_output_kwargs(),
            **_audio_output_kwargs(),
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )

    return speaker_framing
