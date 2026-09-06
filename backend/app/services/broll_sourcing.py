"""Business logic for sourcing B-roll footage from stock providers.

Handles searching Pexels/Pixabay for stock video footage, lightweight
keyword extraction from clip captions/transcripts, and automatically
attaching sourced footage to a Clip as BrollAsset rows.

Results are normalized into a single shape across both providers so the
clip editor can present a real stock-library browser -- poster still,
hover preview, duration, resolution and attribution -- rather than a bare
list of download links.
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

# Words that survive the stopword filter but make useless stock-footage
# queries -- searching Pexels for "something" or "actually" returns either
# nothing or arbitrary filler that has no relation to what is being said.
# B-roll only works when the query names something a camera can point at,
# so discourse markers, hedges and generic abstractions are dropped before
# a keyword is ever sent to a provider.
_NON_VISUAL: frozenset[str] = frozenset(
    {
        "actually", "again", "almost", "already", "also", "although",
        "always", "another", "anyone", "anything", "anyway", "because",
        "become", "before", "believe", "better", "cannot", "certainly",
        "consider", "could", "course", "definitely", "different", "does",
        "doing", "done", "each", "either", "else", "enough", "especially",
        "even", "ever", "every", "everyone", "everything", "exactly",
        "example", "fact", "feel", "first", "from", "gonna", "gotta",
        "great", "guess", "guys", "happen", "hard", "hear", "however",
        "idea", "important", "instead", "issue", "itself", "keep", "kind",
        "know", "last", "least", "less", "little", "look", "lots", "make",
        "many", "matter", "maybe", "mean", "might", "mine", "more", "most",
        "much", "must", "myself", "need", "never", "next", "nice", "nothing",
        "obviously", "often", "okay", "only", "other", "over", "own",
        "part", "perhaps", "please", "point", "possible", "pretty",
        "probably", "quite", "rather", "reason", "remember", "right",
        "same", "say", "says", "second", "see", "seem", "seems", "sense",
        "several", "should", "similar", "simply", "since", "some",
        "somebody", "somehow", "someone", "something", "sometimes",
        "somewhere", "sort", "still", "stuff", "such", "sure", "take",
        "talk", "tell", "thank", "thanks", "that's", "themselves",
        "thing", "things", "think", "those", "though", "thought",
        "through", "thus", "time", "today", "together", "totally", "try",
        "trying", "understand", "until", "usually", "want", "wanted",
        "way", "well", "went", "what's", "whatever", "whether", "while",
        "whole", "whose", "without", "wonder", "would", "yeah",
        "year", "years", "yes", "yourself",
    }
)

_WORD_RE = re.compile(r"[A-Za-z']+")

# Adverbs are never filmable -- "absolutely", "honestly", "completely"
# describe how a thing is said, not anything a camera can point at, and
# they are long, so the length tiebreak below used to promote them over
# the concrete nouns beside them. Dropping every -ly word costs a handful
# of real nouns, which are listed back in.
_LY_NOUNS: frozenset[str] = frozenset(
    {
        "ally", "assembly", "belly", "butterfly", "dragonfly",
        "family", "firefly", "fly", "holly", "jelly", "jewelry", "lily",
        "monopoly", "rally", "reply", "supply", "trolley",
    }
)


def _is_adverb(word: str) -> bool:
    """Whether `word` is (almost certainly) an -ly adverb."""

    return word.endswith("ly") and word not in _LY_NOUNS


# The export canvas is 1080x1920, so a B-roll file wider than this buys
# nothing but download time and decode cost.
_MAX_BROLL_WIDTH = 1920

# A stock clip shorter than this cuts back to the main shot almost as soon
# as it appears, which reads as a glitch rather than a cutaway.
_MIN_BROLL_DURATION = 3.0

# Preview files are streamed straight into a browser <video> in the search
# grid, so they are picked for size, not for quality: the smallest
# rendition that still looks like something in a thumbnail-sized tile.
_MIN_PREVIEW_WIDTH = 360


def _pick_render_variant(variants: list[dict]) -> dict | None:
    """Largest rendition within the export canvas's width budget.

    Anything wider than the canvas costs download time and decode work for
    detail the crop throws away -- a provider's 4K master is a minute of
    extra render time for a 1080-wide frame. Falls back to the smallest
    oversized rendition when every one exceeds the budget.
    """

    if not variants:
        return None
    within_budget = [v for v in variants if 0 < (v.get("width") or 0) <= _MAX_BROLL_WIDTH]
    if within_budget:
        return max(within_budget, key=lambda v: v["width"])
    return min(variants, key=lambda v: v.get("width") or 0)


def _pick_preview_variant(variants: list[dict], fallback: dict | None) -> dict | None:
    """Smallest rendition still legible in a search tile."""

    usable = [v for v in variants if (v.get("width") or 0) >= _MIN_PREVIEW_WIDTH]
    if usable:
        return min(usable, key=lambda v: v["width"])
    return fallback


def _aspect_score(width: int, height: int) -> float:
    """Score how well a source clip survives the crop to a 9:16 canvas.

    Every B-roll file is scaled up and centre-cropped to fill a vertical
    frame, so a landscape clip loses ~70% of its width and a portrait one
    loses almost nothing. Ranking on this is what stops the auto-inserted
    cutaway from being a blown-up sliver of a wide shot.
    """

    if width <= 0 or height <= 0:
        return 0.0
    ratio = width / height
    target = settings.RENDER_WIDTH / settings.RENDER_HEIGHT
    if ratio <= target:
        return 1.0
    # Fraction of the source frame still visible after the centre crop.
    return target / ratio


# Pexels puts a human description in its page URL and leaves `tags` empty
# (e.g. .../video/cleaning-a-coffee-filter-from-the-espresso-machine-13737156/),
# so the slug is the only thing it gives us to judge relevance by.
_PEXELS_SLUG_RE = re.compile(r"/video/([a-z0-9-]+?)-\d+/?$")


def _pexels_description(page_url: str | None) -> str:
    """The human description Pexels encodes in a video's page URL."""

    if not page_url:
        return ""
    match = _PEXELS_SLUG_RE.search(page_url)
    return match.group(1).replace("-", " ") if match else ""


def _relevance(query: str, description: str) -> float:
    """How much of `query` the clip's own description actually accounts for.

    Both providers rank by their own popularity signals, not by fit, so the
    top hit for "espresso machine" is regularly a generic cafe shot that
    merely tags "coffee". Scoring the overlap against the description the
    provider itself publishes -- Pexels' URL slug, Pixabay's tag list --
    promotes the clip that depicts what is being said over the one that is
    merely popular. Returns 0.0 when there is nothing to compare, so a
    provider that gives no description is ranked on the other signals
    rather than penalised into oblivion.
    """

    terms = {w for w in _WORD_RE.findall(query.lower()) if len(w) > 2}
    if not terms or not description:
        return 0.0
    described = set(_WORD_RE.findall(description.lower()))
    return len(terms & described) / len(terms)


def _rank_score(result: dict) -> float:
    """Rank a normalized search result: relevance first, then how well it
    survives the 9:16 crop, then length and resolution.

    Relevance leads because a sharp, perfectly-vertical clip of the wrong
    subject is worse B-roll than a landscape clip of the right one.
    """

    score = _relevance(result.get("keyword") or "", result.get("description") or "") * 300
    score += _aspect_score(result.get("width") or 0, result.get("height") or 0) * 100

    duration = result.get("duration") or 0.0
    if duration and duration < _MIN_BROLL_DURATION:
        score -= 40
    elif duration >= _MIN_BROLL_DURATION * 2:
        score += 10

    # Prefer something at least roughly HD; a 640-wide file looks soft
    # blown up to fill a 1080-wide canvas.
    width = result.get("width") or 0
    if width >= 1080:
        score += 10
    elif width and width < 720:
        score -= 15

    return score


def _pick_pexels_files(video_files: list[dict]) -> tuple[dict | None, dict | None]:
    """Pick the render rendition and the lightweight preview rendition.

    Pexels returns renditions in no useful order, and its first entry is
    frequently a 640x360 SD file -- which looks soft blown up next to CRF 18
    main footage. Prefer the largest file at or below the export canvas
    width for rendering, and the smallest usable file for the browser
    preview so the search grid does not stream HD video per tile.
    """

    usable = [f for f in video_files if f.get("link")]
    if not usable:
        return None, None

    best = _pick_render_variant(usable)
    return best, _pick_preview_variant(usable, best)


async def search_pexels(query: str, per_page: int = 10) -> list[dict]:
    """Search Pexels video library for `query`, returning normalized results.

    Asks for portrait footage first, since these clips are composited onto a
    9:16 canvas, and widens to any orientation when portrait alone does not
    fill the page -- Pexels has far less vertical stock than landscape, so a
    portrait-only search silently returns almost nothing for most queries.

    Degrades gracefully: on any request/parse failure this logs a warning
    and returns an empty list instead of raising, so a Pexels outage doesn't
    take down a combined search that also queries Pixabay.
    """

    if not settings.PEXELS_API_KEY:
        logger.warning("search_pexels called without PEXELS_API_KEY configured")
        return []

    headers = {"Authorization": settings.PEXELS_API_KEY}

    async def _fetch(params: dict[str, str | int]) -> list[dict]:
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
        return _parse_pexels(data, query)

    base: dict[str, str | int] = {"query": query, "per_page": per_page}
    results = await _fetch({**base, "orientation": "portrait"})
    if len(results) < per_page:
        seen = {r["source_asset_id"] for r in results}
        for extra in await _fetch(base):
            if extra["source_asset_id"] not in seen:
                seen.add(extra["source_asset_id"])
                results.append(extra)

    results.sort(key=_rank_score, reverse=True)
    return results[:per_page]


def _parse_pexels(data: dict, query: str) -> list[dict]:
    """Normalize one Pexels search payload into result dicts."""

    results: list[dict] = []
    for video in data.get("videos", []):
        best, preview = _pick_pexels_files(video.get("video_files") or [])
        # `video["url"]` is the Pexels *web page*, not a media file --
        # falling back to it stores an HTML document as asset_url, which
        # ffmpeg then fails to decode at render time. Skip instead.
        if best is None:
            continue
        results.append(
            {
                "source": "pexels",
                "source_asset_id": str(video.get("id")),
                "asset_url": best["link"],
                "preview_url": (preview or best)["link"],
                "thumbnail_url": video.get("image"),
                "provider_url": video.get("url"),
                "author": (video.get("user") or {}).get("name"),
                "description": " ".join(video.get("tags") or [])
                or _pexels_description(video.get("url")),
                "width": best.get("width") or video.get("width"),
                "height": best.get("height") or video.get("height"),
                "duration": float(video.get("duration") or 0.0),
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
        # Real footage only: "animation" hits are motion graphics, which
        # read as clip art dropped into a talking-head short.
        "video_type": "film",
        "safesearch": "true",
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
        # Pixabay returns an entry for every size but leaves `url` empty
        # for the ones it hasn't rendered, so filter before ranking. Size
        # is then chosen against the export canvas rather than by name:
        # "large" is routinely a 4K master, and an upscaled "tiny" is
        # visibly soft next to the CRF 18 main footage.
        available = [
            v
            for v in videos.values()
            if isinstance(v, dict) and v.get("url")
        ]
        variant = _pick_render_variant(available)
        preview = _pick_preview_variant(available, variant)
        if variant is None:
            continue
        results.append(
            {
                "source": "pixabay",
                "source_asset_id": str(hit.get("id")),
                "asset_url": variant["url"],
                "preview_url": (preview or variant)["url"],
                "thumbnail_url": variant.get("thumbnail") or None,
                "provider_url": hit.get("pageURL"),
                "author": hit.get("user"),
                "description": hit.get("tags") or "",
                "width": variant.get("width"),
                "height": variant.get("height"),
                "duration": float(hit.get("duration") or 0.0),
                "keyword": query,
            }
        )

    results.sort(key=_rank_score, reverse=True)
    return results


def extract_keywords(text: str, max_keywords: int = 3) -> list[str]:
    """Extract up to `max_keywords` search-worthy keywords from `text`.

    MVP heuristic: lowercase, strip punctuation, drop stopwords, filler and
    short tokens, then rank by (frequency, word length) so common-but-
    meaningful words win ties over short ones. No POS tagging or stemming.
    The `_NON_VISUAL` filter is what keeps the query naming something
    filmable -- without it the top-ranked token of a typical transcript is
    a hedge like "actually", and every provider search comes back with
    footage unrelated to what is being said.
    """

    if not text:
        return []

    tokens = [w.lower() for w in _WORD_RE.findall(text)]
    candidates = [
        w
        for w in tokens
        if len(w) > 3
        and w not in _STOPWORDS
        and w not in _NON_VISUAL
        and not _is_adverb(w)
    ]
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


def extract_search_phrase(text: str, max_words: int = 2) -> str:
    """Build one multi-word stock-footage query out of `text`.

    Stock libraries index scenes, not vocabulary: "espresso machine"
    retrieves the shot someone is actually describing, while the single
    word "machine" retrieves industrial equipment. This picks the top
    `max_words` keywords and emits them **in the order they were spoken**,
    so the query reads as a phrase a person would type rather than a bag
    of ranked tokens.
    """

    tokens = [w.lower() for w in _WORD_RE.findall(text)]
    keep = [
        w
        for w in tokens
        if len(w) > 3
        and w not in _STOPWORDS
        and w not in _NON_VISUAL
        and not _is_adverb(w)
    ]
    if not keep:
        return ""
    if max_words < 2:
        return keep[0]

    # Prefer words that actually sit next to each other in the sentence.
    # Two adjacent survivors are nearly always a real noun phrase --
    # "espresso machine", "stock market", "operating room" -- whereas the
    # two highest-ranked words taken independently are just as often
    # unrelated ("crashed selling"). Ranking alone can't see this: within
    # one sentence every word has frequency 1, so the tiebreak falls to
    # word length, which prefers whichever noun happens to be longer.
    keepable = set(keep)
    pairs = [
        (first, second)
        for first, second in zip(tokens, tokens[1:], strict=False)
        if first in keepable and second in keepable and first != second
    ]
    if pairs:
        # Among adjacent pairs, prefer one with no past-tense verb in it:
        # "the surgeon walked into the operating room" offers both
        # "surgeon walked" and "operating room", and only the second names
        # something to point a camera at.
        nouny = [p for p in pairs if not any(w.endswith("ed") for w in p)]
        first, second = (nouny or pairs)[0]
        return f"{first} {second}"

    return " ".join(keep[:max_words])


def _extract_keywords_with_timing(
    clip: Clip, max_keywords: int = 20
) -> list[tuple[str, float, float]]:
    """Extract search keywords paired with timestamps that span the whole clip.

    One window per spoken segment overlapping the clip, snapped edge to
    edge so B-roll covers the clip back to back -- from 0 to the first
    window's original start, through any pause between segments, to
    clip_duration after the last one -- rather than only the handful of
    seconds near the start that a hard 3-keyword cap used to leave
    everything else silently uncovered.

    `max_keywords` is a safety cap, not a target: a heavily-segmented
    transcript stops here rather than firing unbounded concurrent provider
    searches (see `auto_source_broll`) or building an unbounded ffmpeg
    filter graph.
    """
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
        words = extract_keywords(clip.caption_text or "", max_keywords=3)
        seg_len = clip_duration / max(len(words), 1)
        return [(w, round(i * seg_len, 2), round((i + 1) * seg_len, 2)) for i, w in enumerate(words)]

    keyword_timings: list[tuple[str, float, float]] = []
    last_phrase: str | None = None

    for seg in segments:
        # One phrase per spoken segment: the sentence is the context that
        # makes a stock search specific, and splitting it into separate
        # one-word searches throws that context away. A segment whose own
        # words are all stopwords/filler carries the previous segment's
        # phrase forward instead of leaving its stretch of the clip with
        # no B-roll window at all.
        phrase = extract_search_phrase(seg.text, max_words=2) or last_phrase
        if not phrase:
            continue
        last_phrase = phrase

        rel_start = max(0.0, round(seg.start_time - clip.start_time, 2))
        rel_end = min(clip_duration, round(seg.end_time - clip.start_time, 2))
        if rel_end <= rel_start:
            continue

        keyword_timings.append((phrase, rel_start, rel_end))
        if len(keyword_timings) >= max_keywords:
            break

    if not keyword_timings:
        return []

    # Snap edge to edge: no gap before the first window, between windows
    # (a pause in speech), or after the last one.
    kw, _, end = keyword_timings[0]
    keyword_timings[0] = (kw, 0.0, end)
    for i in range(len(keyword_timings) - 1):
        kw, start, _ = keyword_timings[i]
        next_start = keyword_timings[i + 1][1]
        keyword_timings[i] = (kw, start, next_start)
    kw, start, _ = keyword_timings[-1]
    keyword_timings[-1] = (kw, start, clip_duration)

    return keyword_timings


async def auto_source_broll(db: Session, clip: Clip) -> list[BrollAsset]:
    """Automatically source and attach B-roll footage timed precisely to spoken words.

    Extracts keywords from the clip's transcript segments along with their
    spoken timestamps, searches Pexels and Pixabay, and inserts BrollAsset
    rows positioned exactly at the moment each keyword is spoken.

    Picks the best-ranked result per keyword (see `_rank_score`) and never
    reuses the same stock clip twice in one short -- neighbouring keywords
    from the same sentence routinely return the same top hit, and seeing it
    cut in twice is more distracting than having no B-roll at all.

    Replaces this clip's previous auto-generated batch (if any) rather than
    adding to it, so re-running this -- the editor's "Auto-insert B-roll"
    button -- regenerates instead of piling duplicates on top of what's
    already there. B-roll the user added manually via search is never
    touched, since only rows this function created are marked
    `auto_generated`.
    """

    kw_timings = _extract_keywords_with_timing(clip)
    if not kw_timings:
        logger.info("No keywords extracted for clip_id=%s; skipping auto-source", clip.id)
        return []

    search_results = await asyncio.gather(
        *(_search_all_providers(kw) for kw, _, _ in kw_timings)
    )

    created: list[BrollAsset] = []
    used: set[tuple[str, str]] = set()
    for (kw, pos_start, pos_end), results in zip(kw_timings, search_results):
        window = pos_end - pos_start
        pick = _choose_asset(results, used, window)
        if pick is None:
            logger.info("No usable B-roll found for keyword=%r on clip_id=%s", kw, clip.id)
            continue

        used.add((pick["source"], pick["source_asset_id"]))
        asset = BrollAsset(
            clip_id=clip.id,
            source=BrollSource(pick["source"]),
            source_asset_id=pick["source_asset_id"],
            asset_url=pick["asset_url"],
            keyword=kw,
            position_start=pos_start,
            position_end=pos_end,
            auto_generated=True,
        )
        created.append(asset)

    if created:
        db.query(BrollAsset).filter(
            BrollAsset.clip_id == clip.id, BrollAsset.auto_generated.is_(True)
        ).delete(synchronize_session=False)
        db.add_all(created)
        db.commit()
        for asset in created:
            db.refresh(asset)
    return created


def _choose_asset(
    results: list[dict], used: set[tuple[str, str]], window: float
) -> dict | None:
    """Pick the best unused result, preferring one long enough to fill `window`."""

    fresh = [r for r in results if (r["source"], r["source_asset_id"]) not in used]
    if not fresh:
        return None

    long_enough = [r for r in fresh if (r.get("duration") or 0.0) >= window]
    return (long_enough or fresh)[0]


async def _search_all_providers(keyword: str, per_page: int = 5) -> list[dict]:
    """Search Pexels and Pixabay concurrently for `keyword`, combining results.

    Merges both providers into one ranked list rather than concatenating
    them, so the top pick is the footage that best survives the 9:16 crop
    regardless of which library it came from. Either provider failing or
    returning empty degrades gracefully rather than aborting the search.
    """

    pexels_results, pixabay_results = await asyncio.gather(
        search_pexels(keyword, per_page=per_page),
        search_pixabay(keyword, per_page=per_page),
    )
    combined = [*pexels_results, *pixabay_results]
    combined.sort(key=_rank_score, reverse=True)
    return combined
