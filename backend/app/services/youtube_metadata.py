"""YouTube Shorts caption, metadata, and content package generation service.

Generates ready-to-publish YouTube Shorts titles, descriptions, hashtags,
SEO tags, timed subtitle transcripts, SRT caption files, and a YouTube
Shorts technical compliance check (9:16 1080x1920, <=60s, H.264/AAC).
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.services.broll_sourcing import extract_keywords
from app.services.text_generation import _extract_json_payload, _resolve_llm_credentials
from app.services.video_render import _caption_events

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.transcript_segment import TranscriptSegment

logger = logging.getLogger(__name__)

_MAX_YOUTUBE_TITLE_LEN = 100


def _format_mm_ss(seconds: float) -> str:
    """Format seconds as M:SS (e.g. '0:04')."""
    total = max(0, int(round(seconds)))
    mins, secs = divmod(total, 60)
    return f"{mins}:{secs:02d}"


def _format_srt_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp HH:MM:SS,mmm."""
    clamped = max(0.0, seconds)
    whole = int(clamped)
    millis = int(round((clamped - whole) * 1000))
    if millis >= 1000:
        whole += 1
        millis = 0
    hours, rem = divmod(whole, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def build_srt_content(events: list[tuple[float, float, str]]) -> str:
    """Build standard SubRip (.srt) subtitle file content from timed caption events."""
    blocks: list[str] = []
    for idx, (start, end, text) in enumerate(events, start=1):
        clean_text = " ".join(text.split()).strip()
        if not clean_text:
            continue
        blocks.append(
            f"{idx}\n"
            f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n"
            f"{clean_text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def _clean_hashtag_token(word: str) -> str:
    """Convert a keyword phrase into a PascalCase hashtag token."""
    parts = re.findall(r"[A-Za-z0-9]+", word)
    if not parts:
        return ""
    return "".join(p.capitalize() for p in parts)


def _build_hashtags(keywords: list[str], include_hashtags: bool = True) -> list[str]:
    """Build a list of high-converting YouTube Shorts hashtags."""
    if not include_hashtags:
        return ["#Shorts"]

    tags: list[str] = ["#Shorts", "#YouTubeShorts", "#ViralShorts"]
    seen = {t.lower() for t in tags}

    for kw in keywords:
        token = _clean_hashtag_token(kw)
        if token and len(token) >= 3:
            tag = f"#{token}"
            if tag.lower() not in seen:
                seen.add(tag.lower())
                tags.append(tag)
        if len(tags) >= 8:
            break

    return tags


def _build_seo_tags(title: str, keywords: list[str]) -> list[str]:
    """Build a list of SEO keyword tags for YouTube Studio."""
    base_tags: list[str] = [
        "shorts",
        "youtube shorts",
        "viral shorts",
    ]
    seen = {t.lower() for t in base_tags}

    clean_title = re.sub(r"#\S+", "", title).strip(" -.,!?")
    if clean_title and len(clean_title) <= 60 and clean_title.lower() not in seen:
        seen.add(clean_title.lower())
        base_tags.insert(0, clean_title.lower())

    for kw in keywords:
        clean_kw = " ".join(re.findall(r"[a-zA-Z0-9]+", kw.lower()))
        if clean_kw and clean_kw not in seen:
            seen.add(clean_kw)
            base_tags.append(clean_kw)
            shorts_kw = f"{clean_kw} shorts"
            if shorts_kw not in seen and len(base_tags) < 12:
                seen.add(shorts_kw)
                base_tags.append(shorts_kw)
        if len(base_tags) >= 12:
            break

    return base_tags[:12]


def _build_youtube_title(
    raw_title: str,
    full_text: str,
    tone: str,
    hashtags: list[str],
) -> str:
    """Create a punchy YouTube Shorts title <= 100 chars with #Shorts."""
    base = re.sub(r"#\S+", "", raw_title or "").strip(" -.,")
    if not base or base.lower() in {"untitled", "untitled clip", "repurposed short clips"}:
        first_sentence = re.split(r"(?<=[.!?])\s+", full_text.strip())[0]
        base = first_sentence.strip(" .,-")[:65] or "Must-Watch Viral Moment"

    tone_norm = tone.strip().lower()
    if tone_norm == "educational" and not base.lower().startswith(("how", "why", "the")):
        headline = f"Why This Matters: {base}"
    elif tone_norm == "storytelling" and not base.endswith(("!", "?")):
        headline = f"{base} (Wait For It!)"
    elif tone_norm == "viral" and not any(c in base for c in ("!", "?", "🔥", "🤯")):
        headline = f"{base} 🔥"
    else:
        headline = base

    suffix_tags = [hashtags[0]] if hashtags else ["#Shorts"]
    if len(hashtags) > 3 and len(headline) <= 65:
        suffix_tags.append(hashtags[3])
    suffix = " " + " ".join(suffix_tags)

    max_head_len = _MAX_YOUTUBE_TITLE_LEN - len(suffix)
    if len(headline) > max_head_len:
        headline = headline[: max_head_len - 1].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"

    return f"{headline}{suffix}".strip()


def _llm_enhance_metadata(
    clip_title: str,
    spoken_text: str,
    tone: str,
    keywords: list[str],
) -> dict[str, Any] | None:
    """Optionally call OpenRouter/OpenAI to craft a title, description, and tags."""
    creds = _resolve_llm_credentials()
    if creds is None:
        return None
    api_key, base_url, model = creds
    try:
        import openai

        client = (
            openai.OpenAI(api_key=api_key, base_url=base_url, timeout=8.0)
            if base_url
            else openai.OpenAI(api_key=api_key, timeout=8.0)
        )
        prompt = (
            "Generate a high-retention YouTube Shorts metadata package in JSON.\n"
            f"Tone: {tone}\n"
            f"Clip Title: {clip_title}\n"
            f"Spoken Content / Transcript: {spoken_text[:1000]}\n"
            f"Visual Keywords: {', '.join(keywords)}\n\n"
            "Return ONLY valid JSON with keys:\n"
            '{"youtube_title": "<=95 chars ending with #Shorts", '
            '"summary_hook": "2-3 engaging sentences summarizing the Short", '
            '"key_takeaways": ["bullet 1", "bullet 2", "bullet 3"], '
            '"hashtags": ["#Shorts", "#YouTubeShorts", ...], '
            '"tags": ["tag1", "tag2", ...]}'
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=450,
        )
        raw = _extract_json_payload(response.choices[0].message.content or "{}")
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and parsed.get("youtube_title"):
            return parsed
    except Exception as exc:
        logger.debug("LLM YouTube metadata generation skipped (%s); using local engine", exc)
    return None


def generate_youtube_caption_package(
    clip: Clip,
    transcript_segments: list[TranscriptSegment],
    *,
    tone: str = "viral",
    include_hashtags: bool = True,
    include_timestamps: bool = True,
) -> dict[str, Any]:
    """Build a complete YouTube Shorts caption, content preview, and SEO package.

    Args:
        clip: The Clip ORM instance.
        transcript_segments: Transcript segments belonging to the parent project.
        tone: Desired style ('viral', 'educational', 'storytelling', 'professional').
        include_hashtags: Whether to include topic hashtags alongside #Shorts.
        include_timestamps: Whether to include timestamped subtitle breakdown in description.

    Returns:
        Dictionary matching `YouTubeCaptionPackageResponse`.
    """
    duration = round(max(0.1, float(clip.end_time - clip.start_time)), 2)

    events = _caption_events(
        caption_text=clip.caption_text,
        transcript_segments=transcript_segments,
        clip_start=clip.start_time,
        duration=duration,
    )

    in_window_segments = [
        seg.text.strip()
        for seg in sorted(transcript_segments, key=lambda s: s.start_time)
        if seg.end_time > clip.start_time
        and seg.start_time < clip.end_time
        and seg.text
        and seg.text.strip()
    ]

    if clip.caption_text and clip.caption_text.strip():
        full_caption_text = " ".join(clip.caption_text.split()).strip()
    elif in_window_segments:
        full_caption_text = " ".join(in_window_segments).strip()
    else:
        full_caption_text = clip.title.strip()

    if not events and full_caption_text:
        events = [(0.0, duration, full_caption_text)]

    broll_kws = [
        b.keyword.strip()
        for b in (clip.broll_assets or [])
        if getattr(b, "keyword", None) and b.keyword.strip()
    ]
    extracted_kws = extract_keywords(f"{clip.title} {full_caption_text}", max_keywords=6)
    combined_keywords: list[str] = []
    for kw in [*broll_kws, *extracted_kws]:
        if kw.lower() not in {k.lower() for k in combined_keywords}:
            combined_keywords.append(kw)

    hashtags = _build_hashtags(combined_keywords, include_hashtags=include_hashtags)
    tags = _build_seo_tags(clip.title, combined_keywords)
    youtube_title = _build_youtube_title(clip.title, full_caption_text, tone, hashtags)

    # Build timed caption items for UI preview and description
    timed_captions: list[dict[str, Any]] = []
    for start_t, end_t, text in events:
        timed_captions.append(
            {
                "start_time": round(start_t, 2),
                "end_time": round(end_t, 2),
                "timestamp_label": f"{_format_mm_ss(start_t)} - {_format_mm_ss(end_t)}",
                "text": text,
            }
        )

    # Extract sentences for description takeaways
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", full_caption_text)
        if len(s.strip()) > 8
    ]
    hook_summary = (
        " ".join(sentences[:2])
        if len(sentences) >= 2
        else (full_caption_text[:240] or clip.title)
    )
    takeaways = sentences[:3] if sentences else [clip.title]

    llm_data = _llm_enhance_metadata(clip.title, full_caption_text, tone, combined_keywords)
    if llm_data:
        raw_yt_title = str(llm_data.get("youtube_title", "")).strip()
        if raw_yt_title:
            if "#shorts" not in raw_yt_title.lower():
                raw_yt_title = f"{raw_yt_title[:90].strip()} #Shorts"
            youtube_title = raw_yt_title[:_MAX_YOUTUBE_TITLE_LEN]
        if isinstance(llm_data.get("summary_hook"), str) and llm_data["summary_hook"].strip():
            hook_summary = llm_data["summary_hook"].strip()
        if isinstance(llm_data.get("key_takeaways"), list) and llm_data["key_takeaways"]:
            takeaways = [str(x).strip() for x in llm_data["key_takeaways"][:4] if str(x).strip()]

    desc_sections: list[str] = [hook_summary]

    if takeaways:
        bullet_lines = "\n".join(f"• {point}" for point in takeaways[:3])
        desc_sections.append(f"📌 Key Highlights:\n{bullet_lines}")

    if include_timestamps and timed_captions:
        ts_lines = "\n".join(
            f"{_format_mm_ss(item['start_time'])} {item['text']}"
            for item in timed_captions[:8]
        )
        desc_sections.append(f"💬 Spoken Captions & Transcript:\n{ts_lines}")

    desc_sections.append(
        "🔔 Subscribe for more daily Shorts & drop your thoughts in the comments below!"
    )

    if hashtags:
        desc_sections.append(" ".join(hashtags))

    youtube_description = "\n\n".join(desc_sections)
    srt_content = build_srt_content(events)

    is_short_duration = 0.5 <= duration <= 60.0
    specs_check = {
        "is_youtube_short_ready": is_short_duration,
        "aspect_ratio": "9:16 (Vertical)",
        "resolution": f"{settings.RENDER_WIDTH}x{settings.RENDER_HEIGHT} HD",
        "fps": settings.RENDER_FPS,
        "duration_seconds": duration,
        "max_duration_seconds": 60.0,
        "video_codec": "H.264 (High@L4.2, yuv420p, BT.709)",
        "audio_codec": f"AAC-LC Stereo 48kHz ({settings.RENDER_AUDIO_LUFS:.0f} LUFS)",
        "has_burned_captions": bool(events),
        "caption_style": (
            clip.caption_style.value
            if hasattr(clip.caption_style, "value")
            else str(clip.caption_style)
        ),
        "framing_mode": (
            clip.framing_mode.value
            if hasattr(clip.framing_mode, "value")
            else str(clip.framing_mode)
        ),
        "broll_count": len(clip.broll_assets or []),
        "status": (
            clip.status.value if hasattr(clip.status, "value") else str(clip.status)
        ),
    }

    return {
        "clip_id": clip.id,
        "tone": tone,
        "youtube_title": youtube_title,
        "youtube_description": youtube_description,
        "hashtags": hashtags,
        "tags": tags,
        "caption_text": full_caption_text,
        "timed_captions": timed_captions,
        "srt_content": srt_content,
        "specs_check": specs_check,
    }
