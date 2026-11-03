"""Voice transcription endpoint for the web chat fallback."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.schemas import VoiceTranscriptionResponse
from app.services.voice import (
    VoiceFeatureDisabledError,
    VoiceTranscriptionError,
    get_voice_service,
)

router = APIRouter(tags=["voice"])


@router.post("/voice/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(
    audio: UploadFile = File(...),  # noqa: B008
    language: str | None = Form(default=None),
) -> VoiceTranscriptionResponse:
    """Transcribe an uploaded audio clip without filing it automatically."""

    if audio.content_type and not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="An audio file is required")
    settings = get_settings()
    suffix = Path(audio.filename or "voice.webm").suffix or ".webm"
    temporary_path: Path | None = None
    try:
        contents = await audio.read()
        if len(contents) > settings.max_voice_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Audio file is too large")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_file.write(contents)
            temporary_path = Path(temporary_file.name)
        result = get_voice_service().transcribe(temporary_path, language)
        return VoiceTranscriptionResponse(
            transcript=result.text,
            detected_language=result.detected_language,
            provider=result.provider,
        )
    except VoiceFeatureDisabledError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except VoiceTranscriptionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
