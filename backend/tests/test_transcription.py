"""Tests for app.services.transcription."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.services.transcription import TranscriptionError, transcribe_video


class TestMissingApiKey:
    @pytest.mark.asyncio
    async def test_falls_back_to_dev_transcript_outside_production(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "")
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")

        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"not a real video, ffmpeg.probe will fail and that's fine")

        segments = await transcribe_video(str(video_file))

        assert len(segments) > 0
        assert all({"start_time", "end_time", "text"} <= seg.keys() for seg in segments)

    @pytest.mark.asyncio
    async def test_raises_in_production_instead_of_faking_data(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing key in production must fail loudly -- the fallback
        transcript is generic placeholder text, not derived from the real
        video, so silently using it would produce fabricated "highlights"
        for real users with no visible error."""

        monkeypatch.setattr(settings, "TRANSCRIPTION_API_KEY", "")
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")

        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"irrelevant")

        with pytest.raises(TranscriptionError, match="TRANSCRIPTION_API_KEY"):
            await transcribe_video(str(video_file))


class TestFileNotFound:
    @pytest.mark.asyncio
    async def test_raises_when_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(TranscriptionError, match="File not found"):
            await transcribe_video(str(tmp_path / "does-not-exist.mp4"))
