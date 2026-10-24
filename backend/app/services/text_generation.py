"""AI-powered script generation for the text-to-shorts pipeline.

Produces structured short-form video stories (~25–35 seconds each) complete
with:
1. Multi-beat story narration (Hook, Development, Twist/Detail, Conclusion).
2. Dynamic visual scene keywords for B-roll sourcing (3–5 distinct visual scenes per short).
3. Exact pacing designed for short-form video platforms (Shorts, Reels, TikTok).

Supports:
- OpenRouter Free mode (``OPENROUTER_API_KEY`` configured, or ``OPENAI_API_KEY``
  starting with ``sk-or-``): Defaults to ``openrouter/free`` with automatic
  failover across top ``:free`` models on OpenRouter.
- OpenAI mode (``OPENAI_API_KEY`` configured): Uses ``gpt-4o-mini`` to write
  vivid, punchy storytelling scripts.
- Smart Story Heuristic Engine (zero-config local mode): Expands prompt ideas
  into structured 4-scene narrative scripts with targeted B-roll keywords.
"""

from __future__ import annotations

import json
import logging
import re
import textwrap

logger = logging.getLogger(__name__)

_FREE_OPENROUTER_FALLBACK_MODELS: tuple[str, ...] = (
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
)


class ScriptSegment:
    """One short-form segment: title, narration, visual keywords, target duration."""

    def __init__(
        self,
        index: int,
        title: str,
        narration: str,
        keywords: list[str],
        duration_seconds: float = 30.0,
    ) -> None:
        self.index = index
        self.title = title
        self.narration = narration
        self.keywords = keywords
        self.duration_seconds = duration_seconds

    def __repr__(self) -> str:
        return (
            f"<ScriptSegment {self.index} title={self.title!r} "
            f"duration={self.duration_seconds}s keywords={self.keywords}>"
        )


def _resolve_llm_credentials() -> tuple[str, str | None, str] | None:
    """Return `(api_key, base_url, model)` for OpenRouter or OpenAI if configured."""
    from app.config import settings

    openrouter_key = getattr(settings, "OPENROUTER_API_KEY", "").strip()
    openai_key = getattr(settings, "OPENAI_API_KEY", "").strip()
    base_url = getattr(
        settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
    ).strip()
    model = getattr(settings, "OPENROUTER_MODEL", "openrouter/free").strip()

    if openrouter_key:
        return openrouter_key, base_url, (model or "openrouter/free")
    if openai_key.startswith("sk-or-"):
        return openai_key, base_url, (model or "openrouter/free")
    if openai_key:
        return openai_key, None, "gpt-4o-mini"
    return None


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def generate_script(
    title: str,
    description: str,
    shorts_count: int,
) -> list[ScriptSegment]:
    """Generate ``shorts_count`` complete short-form video stories.

    Tries OpenRouter (free models) / OpenAI first if an API key is configured,
    otherwise uses the smart procedural story generator.
    """
    creds = _resolve_llm_credentials()
    if creds is not None:
        api_key, base_url, model = creds
        try:
            return _openai_generate(
                title,
                description,
                shorts_count,
                api_key,
                base_url=base_url,
                model=model,
            )
        except Exception:
            logger.exception(
                "LLM script generation failed — falling back to smart story engine"
            )

    return _heuristic_generate(title, description, shorts_count)


# ---------------------------------------------------------------------------
# OpenRouter / OpenAI path
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = textwrap.dedent("""
    You are a master viral Short-form video storyteller for YouTube Shorts, TikTok, and Reels.
    Given a topic title and outline, you generate a JSON array of complete short-form video stories.
    Each item in the array is ONE complete, self-contained Short (around 25 to 35 seconds long).

    Rules for EACH Short:
    - Narration MUST be 60 to 80 words (roughly 25 to 35 seconds of spoken voiceover).
    - Story Arc:
      1. First 3 words: a shocking hook question or bold statement.
      2. Development: fascinating explanation or real-world example.
      3. Twist / Comparison: surprising visual detail or scale.
      4. Climax / Conclusion: quick memorable takeaway.
    - Provide 3 to 4 distinct "keywords" (concrete visual noun phrases for stock footage searches).
    - Return ONLY a valid JSON array.

    Required JSON structure:
    [
      {
        "title": "Short punchy headline (e.g. Rogue Planets in Deep Space)",
        "narration": "Full narration line spoken continuously (60-80 words)",
        "keywords": [
          "space galaxy dark", "frozen planet stars", "deep ocean underwater", "telescope cosmos"
        ],
        "duration_seconds": 30
      }
    ]
""").strip()


def _extract_json_payload(raw: str) -> str:
    """Extract a JSON array or object from raw LLM output, stripping fences or prose."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    start_arr = cleaned.find("[")
    end_arr = cleaned.rfind("]")
    if start_arr != -1 and end_arr > start_arr:
        return cleaned[start_arr : end_arr + 1]
    return cleaned


def _openai_generate(
    title: str,
    description: str,
    shorts_count: int,
    api_key: str,
    *,
    base_url: str | None = None,
    model: str = "gpt-4o-mini",
) -> list[ScriptSegment]:
    """Call OpenRouter (with free-model failover) or OpenAI chat completions."""
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError("openai package not installed — run `pip install openai`") from exc

    client = (
        openai.OpenAI(api_key=api_key, base_url=base_url)
        if base_url
        else openai.OpenAI(api_key=api_key)
    )

    user_prompt = (
        f"Topic Series: {title}\n"
        f"Description / Ideas: {description}\n\n"
        f"Generate exactly {shorts_count} distinct, full 30-second short-form stories."
    )

    models_to_try = [model]
    if base_url:
        for fallback_model in _FREE_OPENROUTER_FALLBACK_MODELS:
            if fallback_model not in models_to_try:
                models_to_try.append(fallback_model)

    last_exc: Exception | None = None
    raw = "[]"
    for candidate_model in models_to_try:
        try:
            logger.info(
                "Calling LLM (%s via %s) for %d short stories on topic %r",
                candidate_model,
                base_url or "openai",
                shorts_count,
                title,
            )
            kwargs: dict[str, object] = {
                "model": candidate_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1200 * shorts_count,
            }
            if not base_url:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)  # type: ignore[arg-type, call-overload]
            raw = _extract_json_payload(response.choices[0].message.content or "[]")
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Model %s failed (%s); trying next free model if available",
                candidate_model,
                exc,
            )
    else:
        if last_exc is not None:
            raise last_exc

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                parsed = v
                break
        else:
            raise ValueError(f"LLM returned unexpected JSON shape: {raw[:200]}")

    if not isinstance(parsed, list):
        raise ValueError(f"LLM returned non-list JSON: {raw[:200]}")

    segments: list[ScriptSegment] = []
    for i, item in enumerate(parsed[:shorts_count]):
        if not isinstance(item, dict):
            continue
        narration = str(item.get("narration", description)).strip()
        kws = [str(k) for k in item.get("keywords", [title])]
        if len(kws) < 3:
            kws.extend(_extract_keywords(f"{title} {narration}"))

        segments.append(
            ScriptSegment(
                index=i,
                title=str(item.get("title", f"{title} – Part {i + 1}")),
                narration=narration,
                keywords=kws[:4],
                duration_seconds=float(item.get("duration_seconds", 30)),
            )
        )

    while len(segments) < shorts_count:
        i = len(segments)
        segments.append(_build_story_segment(title, description, i, shorts_count))

    return segments[:shorts_count]


# ---------------------------------------------------------------------------
# Smart Story Heuristic Engine (Local & Fallback)
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "for",
        "if", "in", "into", "is", "it", "its", "of", "on", "or", "our",
        "so", "that", "the", "their", "then", "there", "these", "they",
        "this", "to", "was", "we", "were", "what", "when", "where",
        "which", "who", "will", "with", "you", "your", "i", "me", "my",
        "not", "no", "do", "does", "did", "have", "has", "had", "can",
        "just", "like", "get", "got", "about", "up", "out", "all",
    }
)


def _extract_keywords(text: str, max_keywords: int = 4) -> list[str]:
    """Frequency-based keyword extractor for visual search."""
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS]
    freq: dict[str, int] = {}
    for w in filtered:
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: -freq[w])
    return ranked[:max_keywords] if ranked else ["nature", "wildlife", "galaxy", "technology"]


# Curated, high-retention story arcs for common YouTube Shorts themes
_CURATED_THEMES: dict[str, list[dict[str, object]]] = {
    "space": [
        {
            "title": "Rogue Planets Wandering the Void",
            "narration": (
                "Did you know there are trillion-ton rogue planets wandering completely alone "
                "in deep space? Violently ejected from their home solar systems, these "
                "orphaned worlds drift through interstellar darkness with frozen atmospheres. "
                "Yet scientists "
                "believe radioactive decay deep inside their cores keeps subsurface oceans liquid "
                "and warm enough to harbor alien life. Billions of these ghost planets could be "
                "drifting right past our galaxy. Space is truly terrifying!"
            ),
            "keywords": [
                "space galaxy dark", "frozen planet universe", "deep ocean glow",
                "stars cosmos telescope",
            ],
        },
        {
            "title": "The Terrifying Power of Neutron Stars",
            "narration": (
                "What if a single teaspoon of matter weighed more than Mount Everest? When massive "
                "stars collapse in violent supernova explosions, they form ultra-dense neutron "
                "stars spinning hundreds of times per second. Their magnetic fields are so intense "
                "they could dissolve the atoms in your body from thousands of miles away! These "
                "cosmic powerhouses are some of the most extreme objects in our universe."
            ),
            "keywords": [
                "supernova star explosion", "neutron star galaxy", "magnetic field aurora",
                "deep space nebula",
            ],
        },
        {
            "title": "Cosmic Water Clouds in Deep Space",
            "narration": (
                "Floating twelve billion light years away is a cosmic cloud holding more water "
                "than all of Earth's oceans combined! This gargantuan reservoir feeds a "
                "supermassive "
                "black hole quasar, radiating energy equal to a thousand trillion suns. The vapor "
                "stretches hundreds of light-years across space, proving that water has existed "
                "since the dawn of the universe. Follow for more unbelievable cosmic secrets!"
            ),
            "keywords": [
                "black hole quasar space", "cosmic water nebula", "galaxy universe stars",
                "deep space cosmos",
            ],
        },
    ],
    "monkey": [
        {
            "title": "Genius Monkeys Using Stone Tools",
            "narration": (
                "Did you know that wild monkeys have officially entered their own Stone Age? In "
                "South America, capuchin monkeys select heavy quartz anvil stones and carefully "
                "hammer open stubborn palm nuts. Archaeologists discovered they have been passing "
                "this toolcraft down through generations for over three thousand years! Their "
                "problem-solving skills rival early humans. Animal intelligence is truly "
                "astonishing!"
            ),
            "keywords": [
                "monkey chimpanzee nature", "stone tool primitive", "wildlife jungle troop",
                "cute monkey forest",
            ],
        },
        {
            "title": "The Secret Vocal Language of Monkeys",
            "narration": (
                "Monkeys don't just chatter; they speak in sophisticated dialects! Vervet monkeys "
                "use distinct alarm calls for specific predators like leopards, eagles, and "
                "venomous snakes. When a sentry sounds the eagle alarm, the entire troop "
                "immediately looks up and dives into dense bushes for cover. Their communication "
                "system is far closer to human speech than we ever imagined!"
            ),
            "keywords": [
                "monkey face looking", "eagle predator flying", "jungle tree canopy",
                "monkey troop forest",
            ],
        },
        {
            "title": "Master Acrobats of the Jungle Canopy",
            "narration": (
                "Watch closely, because spider monkeys can leap over thirty feet between trees "
                "without missing a beat! Their prehensile tail acts as a powerful fifth hand, "
                "capable of supporting their entire body weight with ease. Swinging high above the "
                "rainforest floor, they navigate treacherous canopy gaps at breakneck speeds. They "
                "are nature's ultimate high-wire daredevils. Share this if you love wildlife!"
            ),
            "keywords": [
                "spider monkey swing", "rainforest jungle tree", "monkey jump branch",
                "wild wildlife nature",
            ],
        },
    ],
}


def _heuristic_generate(
    title: str,
    description: str,
    shorts_count: int,
) -> list[ScriptSegment]:
    """Generate structured, engaging 30-second video stories without external AI."""
    lower_context = f"{title} {description}".lower()

    for theme, stories in _CURATED_THEMES.items():
        if theme in lower_context:
            segments: list[ScriptSegment] = []
            for i in range(shorts_count):
                story = stories[i % len(stories)]
                part_title = (
                    f"{title} – {story['title']}"
                    if shorts_count > 1
                    else str(story["title"])
                )
                raw_kws = story.get("keywords")
                kw_list = [str(k) for k in raw_kws] if isinstance(raw_kws, list) else []
                segments.append(
                    ScriptSegment(
                        index=i,
                        title=part_title,
                        narration=str(story["narration"]),
                        keywords=kw_list,
                        duration_seconds=30.0,
                    )
                )
            return segments

    sub_topics = _split_into_topics(description)
    out_segments: list[ScriptSegment] = []

    for i in range(shorts_count):
        topic = sub_topics[i % len(sub_topics)] if sub_topics else description
        seg = _build_story_segment(title, topic, i, shorts_count)
        out_segments.append(seg)

    return out_segments


def _split_into_topics(text: str) -> list[str]:
    """Extract distinct fact points from numbered lists, semicolons, or sentence groups."""
    numbered = re.split(r"(?:\d+[\.\)]\s*|Fact\s*\d+:?\s*)", text.strip())
    cleaned_numbered = [p.strip(" ,;\n") for p in numbered if len(p.strip(" ,;\n")) > 15]
    if len(cleaned_numbered) >= 2:
        return cleaned_numbered

    clauses = re.split(r"[;•\n]+", text.strip())
    cleaned_clauses = [c.strip(" ,;\n") for c in clauses if len(c.strip(" ,;\n")) > 15]
    if len(cleaned_clauses) >= 2:
        return cleaned_clauses

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if len(s) > 10] or [text]


def _build_story_segment(
    main_title: str,
    topic_text: str,
    index: int,
    total_count: int,
) -> ScriptSegment:
    """Build a complete, captivating ~65-word 4-beat short story around `topic_text`."""
    clean_topic = topic_text.strip(" .!?,;")
    kws = _extract_keywords(f"{main_title} {topic_text}", max_keywords=4)

    hook = f"Did you know this mind-blowing truth about {main_title}?"
    development = (
        f"{clean_topic}. Researchers and scientists have uncovered evidence that fundamentally "
        f"changes the way we understand this phenomenon."
    )
    twist = (
        "When observed in action, the sheer scale and complexity defy conventional wisdom, "
        "pushing the boundaries of what was previously thought possible."
    )
    conclusion = (
        "The world is full of incredible wonders. Follow for more fascinating daily discoveries!"
    )

    narration = f"{hook} {development} {twist} {conclusion}"
    part_title = f"{main_title} — Fact {index + 1}" if total_count > 1 else main_title

    scene_keywords = [
        f"{kws[0]} dramatic" if len(kws) > 0 else "nature landscape",
        f"{kws[1]} detail" if len(kws) > 1 else "technology science",
        f"{kws[2]} motion" if len(kws) > 2 else "wildlife motion",
        f"{kws[0]} cinematic" if len(kws) > 0 else "universe cosmos",
    ]

    return ScriptSegment(
        index=index,
        title=part_title,
        narration=narration,
        keywords=scene_keywords,
        duration_seconds=30.0,
    )
