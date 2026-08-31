"""Business logic for sourcing B-roll footage from stock providers.

Handles searching Pexels/Pixabay for stock video footage, lightweight
keyword extraction from clip captions/transcripts, and automatically
attaching sourced footage to a Clip as BrollAsset rows.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.broll_asset import BrollAsset, BrollSource
from app.models.clip import Clip

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/videos/"

# Minimal English stopword list for MVP keyword extraction. This is a
# frequency/length heuristic, not real NLP (no POS tagging, no stemming).
# Swap this out for a proper NLP library (e.g. spaCy/YAKE) if extraction
# quality becomes a problem.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for",
        "if", "in", "into", "is", "it", "its", "of", "on", "or", "our",
        "so", "that", "the", "their", "then", "there", "these", "they",
        "this", "to", "was", "we", "were", "what", "when", "where",
        "which", "who", "will", "with", "you", "your", "i", "me", "my",
        "not", "no", "do", "does", "did", "have", "has", "had", "can",
        "just", "like", "get", "got", "about", "up", "out", "all",
        "them", "he", "she", "his", "her", "him", "us", "am", "been",
        "being", "here", "than", "too", "very", "really", "one",
    }
)

_WORD_RE = re.compile(r"[A-Za-z']+")


# The export canvas is 1080x1920, so a B-roll file wider than this buys
# nothing but download time and decode cost.
_MAX_BROLL_WIDTH = 1920


def _best_pexels_file(video_files: list[dict]) -> str | None:
    """Pick the highest-resolution Pexels rendition worth downloading.

    Pexels returns renditions in no useful order, and its first entry is
    frequently a 640x360 SD file -- which looks soft blown up next to CRF 18
    main footage. Prefer the largest file at or below the export canvas
    width, falling back to the smallest oversized one if every rendition is
    bigger than that.
    """

    usable = [f for f in video_files if f.get("link")]
    if not usable:
        return None

    within_budget = [f for f in usable if (f.get("width") or 0) <= _MAX_BROLL_WIDTH]
    if within_budget:
        best = max(within_budget, key=lambda f: f.get("width") or 0)
    else:
        best = min(usable, key=lambda f: f.get("width") or 0)
    return best.get("link")


async def search_pexels(query: str, per_page: int = 10) -> list[dict]:
    """Search Pexels video library for `query`, returning normalized results.

    Degrades gracefully: on any request/parse failure this logs a warning
    and returns an empty list instead of raising, so a Pexels outage doesn't
    take down a combined search that also queries Pixabay.
    """

    if not settings.PEXELS_API_KEY:
        logger.warning("search_pexels called without PEXELS_API_KEY configured")
        return []

    headers = {"Authorization": settings.PEXELS_API_KEY}
    params: dict[str, str | int] = {"query": query, "per_page": per_page}

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(PEXELS_SEARCH_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Pexels search failed for query=%r: %s", query, exc)
        return []
    except ValueError as exc:
        logger.warning("Pexels search returned invalid JSON for query=%r: %s", query, exc)
        return []

    results: list[dict] = []
    for video in data.get("videos", []):
        video_files = video.get("video_files") or []
        asset_url = _best_pexels_file(video_files) or video.get("url")
        if not asset_url:
            continue
        results.append(
            {
                "source": "pexels",
                "source_asset_id": str(video.get("id")),
                "asset_url": asset_url,
                "keyword": query,
            }
        )
    return results


async def search_pixabay(query: str, per_page: int = 10) -> list[dict]:
    """Search Pixabay video library for `query`, returning normalized results.

    Degrades gracefully: on any request/parse failure this logs a warning
    and returns an empty list instead of raising.
    """

    if not settings.PIXABAY_API_KEY:
        logger.warning("search_pixabay called without PIXABAY_API_KEY configured")
        return []

    # Pixabay requires per_page in [3, 200].
    safe_per_page = max(3, min(per_page, 200))
    params: dict[str, str | int] = {
        "key": settings.PIXABAY_API_KEY,
        "q": query,
        "per_page": safe_per_page,
    }

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(PIXABAY_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Pixabay search failed for query=%r: %s", query, exc)
        return []
    except ValueError as exc:
        logger.warning("Pixabay search returned invalid JSON for query=%r: %s", query, exc)
        return []

    results: list[dict] = []
    for hit in data.get("hits", []):
        videos = hit.get("videos") or {}
        # Highest quality first: B-roll is composited onto a 1080-wide
        # canvas, and an upscaled "small" variant is visibly soft next to
        # the CRF 18 main footage.
        variant = (
            videos.get("large")
            or videos.get("medium")
            or videos.get("small")
            or videos.get("tiny")
        )
        asset_url = variant.get("url") if variant else None
        if not asset_url:
            continue
        results.append(
            {
                "source": "pixabay",
                "source_asset_id": str(hit.get("id")),
                "asset_url": asset_url,
                "keyword": query,
            }
        )
    return results


def extract_keywords(text: str, max_keywords: int = 3) -> list[str]:
    """Extract up to `max_keywords` search-worthy keywords from `text`.

    MVP heuristic: lowercase, strip punctuation, drop stopwords/short
    tokens, then rank by (frequency, word length) so common-but-meaningful
    words win ties over short ones. No POS tagging or stemming. Good
    enough to drive a stock-footage search query; upgrade to a real NLP
    library later if extraction quality needs improving.
    """

    if not text:
        return []

    tokens = [w.lower() for w in _WORD_RE.findall(text)]
    candidates = [w for w in tokens if len(w) > 3 and w not in _STOPWORDS]
    if not candidates:
        return []

    counts = Counter(candidates)
    ranked = sorted(counts.items(), key=lambda item: (item[1], len(item[0])), reverse=True)

    keywords: list[str] = []
    for word, _count in ranked:
        if word not in keywords:
            keywords.append(word)
        if len(keywords) >= max_keywords:
            break
    return keywords


def _extract_keywords_with_timing(clip: Clip, max_keywords: int = 3) -> list[tuple[str, float, float]]:
    """Extract search keywords paired with their exact spoken occurrence timestamps."""
    video_project = clip.video_project
    clip_duration = clip.end_time - clip.start_time
    if clip_duration <= 0:
        return []

    segments = []
    if video_project and video_project.transcript_segments:
        segments = [
            s
            for s in video_project.transcript_segments
            if s.end_time > clip.start_time and s.start_time < clip.end_time
        ]
        segments.sort(key=lambda s: s.start_time)

    if not segments:
        words = extract_keywords(clip.caption_text or "", max_keywords=max_keywords)
        seg_len = clip_duration / max(len(words), 1)
        return [(w, round(i * seg_len, 2), round((i + 1) * seg_len, 2)) for i, w in enumerate(words)]

    keyword_timings: list[tuple[str, float, float]] = []
    seen_words: set[str] = set()

    for seg in segments:
        seg_words = extract_keywords(seg.text, max_keywords=2)
        rel_start = max(0.0, round(seg.start_time - clip.start_time, 2))
        rel_end = min(clip_duration, max(rel_start + 2.5, round(seg.end_time - clip.start_time, 2)))

        for kw in seg_words:
            if kw not in seen_words:
                seen_words.add(kw)
                keyword_timings.append((kw, rel_start, rel_end))
                if len(keyword_timings) >= max_keywords:
                    break
        if len(keyword_timings) >= max_keywords:
            break

    return keyword_timings


async def auto_source_broll(db: Session, clip: Clip) -> list[BrollAsset]:
    """Automatically source and attach B-roll footage timed precisely to spoken words.

    Extracts keywords from the clip's transcript segments along with their
    spoken timestamps, searches Pexels and Pixabay, and inserts BrollAsset
    rows positioned exactly at the moment each keyword is spoken.
    """

    kw_timings = _extract_keywords_with_timing(clip, max_keywords=3)
    if not kw_timings:
        logger.info("No keywords extracted for clip_id=%s; skipping auto-source", clip.id)
        return []

    search_results = await asyncio.gather(
        *(_search_all_providers(kw) for kw, _, _ in kw_timings)
    )

    created: list[BrollAsset] = []
    for (kw, pos_start, pos_end), results in zip(kw_timings, search_results):
        if not results:
            continue
        pick = results[0]
        asset = BrollAsset(
            clip_id=clip.id,
            source=BrollSource(pick["source"]),
            source_asset_id=pick["source_asset_id"],
            asset_url=pick["asset_url"],
            keyword=kw,
            position_start=pos_start,
            position_end=pos_end,
        )
        db.add(asset)
        created.append(asset)

    if created:
        db.commit()
        for asset in created:
            db.refresh(asset)
    return created


async def _search_all_providers(keyword: str, per_page: int = 5) -> list[dict]:
    """Search Pexels and Pixabay concurrently for `keyword`, combining results.

    Either provider failing/returning empty degrades gracefully rather than
    aborting the whole search.
    """

    pexels_results, pixabay_results = await asyncio.gather(
        search_pexels(keyword, per_page=per_page),
        search_pixabay(keyword, per_page=per_page),
    )
    return [*pexels_results, *pixabay_results]
