"""Tests for translation caching and fallback behavior."""

from app.config import Settings
from app.services.translation import TranslationService


def test_same_language_uses_identity_provider() -> None:
    service = TranslationService()

    result = service.translate("  Water is unavailable.  ", "en", "en")

    assert result.text == "Water is unavailable."
    assert result.provider == "identity"
    assert result.used_fallback is False


def test_local_provider_is_cached() -> None:
    calls: list[tuple[str, str, str]] = []

    def provider(text: str, source: str, target: str) -> str:
        calls.append((text, source, target))
        return "Water is unavailable."

    settings = Settings(enable_translation=True)
    service = TranslationService(settings=settings, local_provider=provider)
    first = service.translate("पानी नहीं है", "hi", "en")
    second = service.translate("पानी नहीं है", "hi", "en")

    assert first.text == second.text == "Water is unavailable."
    assert first.provider == "indictrans2"
    assert len(calls) == 1


def test_external_provider_is_used_after_local_failure() -> None:
    calls: list[str] = []

    def local_provider(text: str, source: str, target: str) -> str:
        raise RuntimeError("local model unavailable")

    def external_provider(text: str, source: str, target: str) -> str:
        calls.append(text)
        return "Translated complaint"

    settings = Settings(enable_translation=True, translation_external_fallback=True)
    service = TranslationService(
        settings=settings,
        local_provider=local_provider,
        external_provider=external_provider,
    )
    result = service.translate("నీరు లేదు", "te", "en")

    assert result.text == "Translated complaint"
    assert result.provider == "external"
    assert calls == ["నీరు లేదు"]


def test_original_text_fallback_is_safe_and_cached() -> None:
    settings = Settings(enable_translation=True, translation_external_fallback=False)
    service = TranslationService(settings=settings, local_provider=lambda *_: (_ for _ in ()).throw(RuntimeError()))

    result = service.translate_for_officer("मुझे पानी चाहिए", "hi")
    cached = service.translate_for_officer("मुझे पानी चाहिए", "hi")

    assert result.text == "मुझे पानी चाहिए"
    assert result.provider == "original_text_fallback"
    assert result.used_fallback is True
    assert cached == result


def test_empty_text_does_not_call_translation_provider() -> None:
    service = TranslationService(local_provider=lambda *_: "should not run")

    result = service.translate("  ", "hi", "en")

    assert result.text == ""
    assert result.provider == "empty"
