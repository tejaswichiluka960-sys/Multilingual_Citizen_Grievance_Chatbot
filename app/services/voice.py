"""Lazy faster-whisper voice transcription service."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class VoiceFeatureDisabledError(RuntimeError):
    """Raised when voice processing is not enabled in configuration."""


class VoiceTranscriptionError(RuntimeError):
    """Raised when an audio file cannot be transcribed."""


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """Transcript and provider metadata returned to the interface."""

    text: str
    detected_language: str | None
    provider: str


class WhisperProvider:
    """Lazy wrapper around faster-whisper."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load(self) -> Any:
        """Load the Whisper model only when the first voice request arrives."""

        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
        return self._model

    def __call__(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        """Transcribe one audio file with faster-whisper."""

        segments, info = self._load().transcribe(str(audio_path), language=language, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        if not text:
            raise VoiceTranscriptionError("No speech was detected in the audio")
        return TranscriptionResult(text=text, detected_language=getattr(info, "language", None), provider="faster-whisper")


class VoiceTranscriptionService:
    """Feature-gated voice transcription with injectable providers."""

    def __init__(self, settings: Settings | None = None, provider: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._provider = provider

    def transcribe(self, audio_path: Path, language: str | None = None) -> TranscriptionResult:
        """Transcribe audio or raise a clear, user-safe service error."""

        if not self.settings.enable_voice:
            raise VoiceFeatureDisabledError("Voice input is disabled; set ENABLE_VOICE=true")
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise VoiceTranscriptionError("Audio file is empty or unavailable")
        if self._provider is None:
            self._provider = WhisperProvider(self.settings.whisper_model)
        try:
            return self._provider(audio_path, language)
        except (VoiceFeatureDisabledError, VoiceTranscriptionError):
            raise
        except Exception as exc:
            logger.exception("Voice transcription failed")
            raise VoiceTranscriptionError("Voice transcription failed") from exc


_service: VoiceTranscriptionService | None = None


def get_voice_service() -> VoiceTranscriptionService:
    """Return the process-wide voice service."""

    global _service
    if _service is None:
        _service = VoiceTranscriptionService()
    return _service
