"""Tests for feature-gated voice transcription."""

from pathlib import Path

import pytest

from app.config import Settings
from app.services.voice import (
    TranscriptionResult,
    VoiceFeatureDisabledError,
    VoiceTranscriptionService,
)


def test_voice_service_uses_injected_provider(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.webm"
    audio_path.write_bytes(b"audio")
    calls: list[tuple[Path, str | None]] = []

    def provider(path: Path, language: str | None) -> TranscriptionResult:
        calls.append((path, language))
        return TranscriptionResult("No water supply", "en", "test-provider")

    service = VoiceTranscriptionService(Settings(enable_voice=True), provider=provider)

    result = service.transcribe(audio_path, "en")

    assert result.text == "No water supply"
    assert result.provider == "test-provider"
    assert calls == [(audio_path, "en")]


def test_voice_service_requires_explicit_enable_flag(tmp_path: Path) -> None:
    audio_path = tmp_path / "voice.webm"
    audio_path.write_bytes(b"audio")
    service = VoiceTranscriptionService(Settings(enable_voice=False), provider=lambda *_: None)

    with pytest.raises(VoiceFeatureDisabledError, match="ENABLE_VOICE=true"):
        service.transcribe(audio_path)
