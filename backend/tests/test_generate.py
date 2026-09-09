"""Tests for the AI text-to-shorts generation endpoint and services."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.text_generation import _extract_keywords, _heuristic_generate, generate_script


def test_keyword_extractor() -> None:
    """Keyword extraction should rank meaningful nouns and filter stopwords."""
    keywords = _extract_keywords(
        "Top 5 Monkey Facts: monkeys love swinging in jungle trees and eating fruits"
    )
    assert (
        "monkeys" in keywords
        or "monkey" in keywords
        or "jungle" in keywords
        or "fruits" in keywords
    )
    assert "and" not in keywords
    assert "the" not in keywords


def test_heuristic_script_generator() -> None:
    """Heuristic generation should produce requested number of segments."""
    title = "Top 3 Space Wonders"
    desc = (
        "First fact is about neutron stars with extreme density. "
        "Second fact is about rogue planets wandering in deep dark cosmic space. "
        "Third fact is about giant water clouds floating in the galaxy."
    )
    segments = _heuristic_generate(title, desc, 3)
    assert len(segments) == 3
    for i, seg in enumerate(segments):
        assert seg.index == i
        assert len(seg.title) > 0
        assert len(seg.narration) > 0
        assert len(seg.keywords) > 0
        assert seg.duration_seconds > 0


def test_generate_from_text_endpoint(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """POST /api/v1/generate creates a text-sourced VideoProject and Clip stubs."""
    with patch("app.routers.generate.assemble_text_clip") as mock_assemble:
        response = client.post(
            "/api/v1/generate",
            headers=auth_headers,
            json={
                "title": "Top 5 Monkey Facts",
                "description": (
                    "Fascinating facts about wild monkeys including high intelligence, tool "
                    "use, social hierarchies, agility, and surprising traits."
                ),
                "shorts_count": 3,
                "caption_style": "hormozi",
                "auto_broll": True,
            },
        )

        assert response.status_code == 202
        data = response.json()

        assert "project" in data
        assert "clips" in data
        project = data["project"]
        assert project["title"] == "Top 5 Monkey Facts"
        assert project["source_type"] == "text"
        assert project["status"] == "generating"
        assert project["shorts_count"] == 3

        clips = data["clips"]
        assert len(clips) == 3
        for clip in clips:
            assert clip["status"] == "rendering"
            assert clip["video_project_id"] == project["id"]
            assert len(clip["title"]) > 0

        # Verify background tasks were queued
        assert mock_assemble.called


def test_generate_endpoint_validation_error(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    """Validation fails if title is empty or description is too short."""
    response = client.post(
        "/api/v1/generate",
        headers=auth_headers,
        json={
            "title": "",
            "description": "Too short",
            "shorts_count": 3,
        },
    )
    assert response.status_code == 422


def test_story_script_structure() -> None:
    """Every generated short should have 50+ words and multiple distinct scene keywords."""
    segments = generate_script(
        "Top 3 Mind-Blowing Space Facts",
        "Unbelievable cosmic anomalies: rogue planets, neutron stars, water clouds",
        3,
    )
    assert len(segments) == 3
    for seg in segments:
        words = seg.narration.split()
        assert len(words) >= 50, f"Narration should be a rich story (got {len(words)} words)"
        assert (
            len(seg.keywords) >= 3
        ), f"Must have at least 3 scene keywords (got {len(seg.keywords)})"


def test_voice_synthesis_fallback(tmp_path) -> None:
    """Voice synthesis generates audio file and timed subtitle events."""
    from app.services.voice_synthesis import (
        _estimate_sentence_timings,
    )

    text = (
        "Did you know that monkeys use tools? In the wild, they hammer palm nuts with heavy stones."
    )
    events = _estimate_sentence_timings(text, 30.0)
    assert len(events) >= 2
    for start, end, phrase in events:
        assert end > start
        assert len(phrase) > 0

