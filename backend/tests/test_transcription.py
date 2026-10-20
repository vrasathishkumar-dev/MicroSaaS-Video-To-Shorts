"""Tests for app.services.transcription.

The contract this module has to keep is narrow and important: it returns
what was actually said, or it raises. Every short the app produces is built
on the transcript -- which moments get cut, what the titles say, what burns
into the captions -- so a plausible-looking invented transcript is the one
failure mode worth testing hardest against.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.config import settings
from app.services.transcription import (
    TranscriptionError,
    _backend,
    _transcribe_locally,
    parse_vtt_subtitles,
    transcribe_video,
)


class TestBackendSelection:
    def test_local_is_used_when_no_api_key_is_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fresh checkout has no key and must still transcribe for real."""

        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "auto")
        monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "")

        assert _backend() == "local"

    def test_the_api_is_used_when_a_key_is_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "auto")
        monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "sk-test")

        assert _backend() == "api"

    def test_an_explicit_choice_overrides_the_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "sk-test")
        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "local")

        assert _backend() == "local"


class TestLocalTranscription:
    @pytest.mark.asyncio
    async def test_a_video_without_a_key_is_transcribed_locally(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "local")
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"stand-in for a real video")

        real = [{"start_time": 0.0, "end_time": 2.5, "text": "What was said"}]
        with patch(
            "app.services.transcription._transcribe_locally", return_value=real
        ) as local:
            segments = await transcribe_video(str(video_file))

        assert segments == real
        local.assert_called_once()

    def test_a_silent_video_fails_instead_of_inventing_words(self) -> None:
        """Whisper over music or silence has nothing to say. An empty
        transcript is a failed job, not a short about nothing."""

        class _Info:
            duration = 30.0
            language = "en"

        with patch(
            "app.services.transcription._local_model",
            return_value=type(
                "_Model",
                (),
                {"transcribe": lambda self, *a, **k: (iter([]), _Info())},
            )(),
        ), pytest.raises(TranscriptionError, match="No speech"):
            _transcribe_locally(Path("audio.mp3"))

    def test_a_missing_whisper_install_says_what_to_do(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "local")

        with patch(
            "app.services.transcription._local_model",
            side_effect=TranscriptionError(
                "Local transcription needs faster-whisper: `pip install "
                "faster-whisper`"
            ),
        ), pytest.raises(TranscriptionError, match="faster-whisper"):
            _transcribe_locally(Path("audio.mp3"))


class TestSidecarVttFallback:
    def test_parses_vtt_subtitles_and_merges_rolling_cues(self, tmp_path: Path) -> None:
        vtt_file = tmp_path / "podcast.en.vtt"
        vtt_file.write_text(
            "WEBVTT\n\n"
            "00:00:00.000 --> 00:00:02.500\n"
            "Here's the secret nobody tells you\n\n"
            "00:00:02.600 --> 00:00:05.200\n"
            "about building a startup from scratch.\n\n"
            "00:00:08.000 --> 00:00:12.000\n"
            "It comes down to distribution and focus.\n",
            encoding="utf-8",
        )
        segments = parse_vtt_subtitles(vtt_file)
        assert len(segments) == 2
        assert segments[0]["start_time"] == 0.0
        assert segments[0]["end_time"] == 5.2
        assert "secret nobody tells you about building" in segments[0]["text"]
        assert segments[1]["start_time"] == 8.0
        assert segments[1]["end_time"] == 12.0

    @pytest.mark.asyncio
    async def test_falls_back_to_sidecar_vtt_when_whisper_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "local")
        video_file = tmp_path / "podcast123.mp4"
        video_file.write_bytes(b"stand-in video")
        vtt_file = tmp_path / "podcast123.en.vtt"
        vtt_file.write_text(
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:04.000\n"
            "Welcome to the podcast episode.\n",
            encoding="utf-8",
        )

        with patch(
            "app.services.transcription._transcribe_locally",
            side_effect=TranscriptionError("faster-whisper not installed"),
        ):
            segments = await transcribe_video(str(video_file))

        assert len(segments) == 1
        assert segments[0]["text"] == "Welcome to the podcast episode."


class TestApiTranscription:
    @pytest.mark.asyncio
    async def test_a_provider_failure_raises_rather_than_faking_a_transcript(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpx

        monkeypatch.setattr(settings, "TRANSCRIPTION_BACKEND", "api")
        monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "sk-test")
        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"stand-in for a real video")

        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("no route to host"),
        ), pytest.raises(TranscriptionError, match="request failed"):
            await transcribe_video(str(video_file))


class TestFileNotFound:
    @pytest.mark.asyncio
    async def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(TranscriptionError, match="File not found"):
            await transcribe_video(str(tmp_path / "does-not-exist.mp4"))
