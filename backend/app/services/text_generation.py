"""AI-powered script generation for the text-to-shorts pipeline.

Produces structured short-form video stories (~25–35 seconds each) complete
with:
1. Multi-beat story narration (Hook, Development, Twist/Detail, Conclusion).
2. Dynamic visual scene keywords for B-roll sourcing (3–5 distinct visual scenes per short).
3. Exact pacing designed for short-form video platforms (Shorts, Reels, TikTok).

Supports:
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


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def generate_script(
    title: str,
    description: str,
    shorts_count: int,
) -> list[ScriptSegment]:
    """Generate ``shorts_count`` complete short-form video stories.

    Tries OpenAI first if an API key is configured, otherwise uses the smart
    procedural story generator.
    """
    from app.config import settings

    if getattr(settings, "OPENAI_API_KEY", None):
        try:
            return _openai_generate(title, description, shorts_count, settings.OPENAI_API_KEY)
        except Exception:
            logger.exception("OpenAI generation failed — falling back to smart story engine")

    return _heuristic_generate(title, description, shorts_count)


# ---------------------------------------------------------------------------
# OpenAI path
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
        "keywords": ["space galaxy dark", "frozen planet stars", "deep ocean underwater", "telescope cosmos"],
        "duration_seconds": 30
      }
    ]
""").strip()


def _openai_generate(
    title: str,
    description: str,
    shorts_count: int,
    api_key: str,
) -> list[ScriptSegment]:
    """Call GPT-4o-mini and parse a JSON array of multi-scene stories."""
    try:
        import openai
    except ImportError as exc:
        raise RuntimeError("openai package not installed — run `pip install openai`") from exc

    client = openai.OpenAI(api_key=api_key)

    user_prompt = (
        f"Topic Series: {title}\n"
        f"Description / Ideas: {description}\n\n"
        f"Generate exactly {shorts_count} distinct, full 30-second short-form stories."
    )

    logger.info("Calling OpenAI gpt-4o-mini for %d short stories on topic %r", shorts_count, title)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=1200 * shorts_count,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "[]"
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                parsed = v
                break
        else:
            raise ValueError(f"OpenAI returned unexpected JSON shape: {raw[:200]}")

    segments: list[ScriptSegment] = []
    for i, item in enumerate(parsed[:shorts_count]):
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

    # Pad if GPT returned fewer than requested
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
                "Did you know there are trillion-ton rogue planets wandering completely alone in deep space? "
                "Violently ejected from their home solar systems, these orphaned worlds drift through interstellar darkness with frozen atmospheres. "
                "Yet scientists believe radioactive decay deep inside their cores keeps subsurface oceans liquid and warm enough to harbor alien life. "
                "Billions of these ghost planets could be drifting right past our galaxy. Space is truly terrifying!"
            ),
            "keywords": ["space galaxy dark", "frozen planet universe", "deep ocean glow", "stars cosmos telescope"],
        },
        {
            "title": "The Terrifying Power of Neutron Stars",
            "narration": (
                "What if a single teaspoon of matter weighed more than Mount Everest? "
                "When massive stars collapse in violent supernova explosions, they form ultra-dense neutron stars spinning hundreds of times per second. "
                "Their magnetic fields are so intense they could dissolve the atoms in your body from thousands of miles away! "
                "These cosmic powerhouses are some of the most extreme objects in our universe."
            ),
            "keywords": ["supernova star explosion", "neutron star galaxy", "magnetic field aurora", "deep space nebula"],
        },
        {
            "title": "Cosmic Water Clouds in Deep Space",
            "narration": (
                "Floating twelve billion light years away is a cosmic cloud holding more water than all of Earth's oceans combined! "
                "This gargantuan reservoir feeds a supermassive black hole quasar, radiating energy equal to a thousand trillion suns. "
                "The vapor stretches hundreds of light-years across space, proving that water has existed since the dawn of the universe. "
                "Follow for more unbelievable cosmic secrets!"
            ),
            "keywords": ["black hole quasar space", "cosmic water nebula", "galaxy universe stars", "deep space cosmos"],
        },
    ],
    "monkey": [
        {
            "title": "Genius Monkeys Using Stone Tools",
            "narration": (
                "Did you know that wild monkeys have officially entered their own Stone Age? "
                "In South America, capuchin monkeys select heavy quartz anvil stones and carefully hammer open stubborn palm nuts. "
                "Archaeologists discovered they have been passing this toolcraft down through generations for over three thousand years! "
                "Their problem-solving skills rival early humans. Animal intelligence is truly astonishing!"
            ),
            "keywords": ["monkey chimpanzee nature", "stone tool primitive", "wildlife jungle troop", "cute monkey forest"],
        },
        {
            "title": "The Secret Vocal Language of Monkeys",
            "narration": (
                "Monkeys don't just chatter; they speak in sophisticated dialects! "
                "Vervet monkeys use distinct alarm calls for specific predators like leopards, eagles, and venomous snakes. "
                "When a sentry sounds the eagle alarm, the entire troop immediately looks up and dives into dense bushes for cover. "
                "Their communication system is far closer to human speech than we ever imagined!"
            ),
            "keywords": ["monkey face looking", "eagle predator flying", "jungle tree canopy", "monkey troop forest"],
        },
        {
            "title": "Master Acrobats of the Jungle Canopy",
            "narration": (
                "Watch closely, because spider monkeys can leap over thirty feet between trees without missing a beat! "
                "Their prehensile tail acts as a powerful fifth hand, capable of supporting their entire body weight with ease. "
                "Swinging high above the rainforest floor, they navigate treacherous canopy gaps at breakneck speeds. "
                "They are nature's ultimate high-wire daredevils. Share this if you love wildlife!"
            ),
            "keywords": ["spider monkey swing", "rainforest jungle tree", "monkey jump branch", "wild wildlife nature"],
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

    # Check curated thematic stories first (for popular examples like monkey / space)
    for theme, stories in _CURATED_THEMES.items():
        if theme in lower_context:
            segments: list[ScriptSegment] = []
            for i in range(shorts_count):
                story = stories[i % len(stories)]
                part_title = f"{title} – {story['title']}" if shorts_count > 1 else str(story["title"])
                segments.append(
                    ScriptSegment(
                        index=i,
                        title=part_title,
                        narration=str(story["narration"]),
                        keywords=[str(k) for k in story["keywords"]],
                        duration_seconds=30.0,
                    )
                )
            return segments

    # Procedural multi-scene story generator for any custom topic
    # 1. Parse individual points from description if the user entered bullet points or commas
    sub_topics = _split_into_topics(description)
    segments: list[ScriptSegment] = []

    for i in range(shorts_count):
        topic = sub_topics[i % len(sub_topics)] if sub_topics else description
        seg = _build_story_segment(title, topic, i, shorts_count)
        segments.append(seg)

    return segments


def _split_into_topics(text: str) -> list[str]:
    """Extract distinct fact points from numbered lists, semicolons, or sentence groups."""
    # Check for numbered items (1., 2., Fact 1:)
    numbered = re.split(r"(?:\d+[\.\)]\s*|Fact\s*\d+:?\s*)", text.strip())
    cleaned_numbered = [p.strip(" ,;\n") for p in numbered if len(p.strip(" ,;\n")) > 15]
    if len(cleaned_numbered) >= 2:
        return cleaned_numbered

    # Check for comma / semicolon separated clauses
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

    # Narrative arc (Hook -> Core explanation -> Fascinating twist -> Punchline)
    hook = f"Did you know this mind-blowing truth about {main_title}?"
    development = (
        f"{clean_topic}. Researchers and scientists have uncovered evidence that fundamentally "
        f"changes the way we understand this phenomenon."
    )
    twist = (
        f"When observed in action, the sheer scale and complexity defy conventional wisdom, "
        f"pushing the boundaries of what was previously thought possible."
    )
    conclusion = f"The world is full of incredible wonders. Follow for more fascinating daily discoveries!"

    narration = f"{hook} {development} {twist} {conclusion}"
    part_title = f"{main_title} — Fact {index + 1}" if total_count > 1 else main_title

    # Generate 4 distinct scene keywords so each scene changes visual footage
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
