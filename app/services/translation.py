"""Translation service with lazy IndicTrans2 loading and safe fallbacks."""

import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

TranslationProvider = Callable[[str, str, str], str]

LANGUAGE_TO_INDIC = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "te": "tel_Telu",
    "hinglish": "hin_Latn",
    "tenglish": "tel_Latn",
}

LANGUAGE_TO_EXTERNAL = {
    "en": "en",
    "hi": "hi",
    "te": "te",
    "hinglish": "hi",
    "tenglish": "te",
}


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Translation output and provider metadata."""

    text: str
    source_language: str
    target_language: str
    provider: str
    used_fallback: bool


class IndicTrans2Provider:
    """Lazy wrapper around the configured Hugging Face translation model."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._pipeline = None

    def _load(self):
        """Load the translation pipeline only on first translation request."""

        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline("translation", model=self.model_name)
        return self._pipeline

    def __call__(self, text: str, source_language: str, target_language: str) -> str:
        """Translate one message through IndicTrans2."""

        translator = self._load()
        source_code = LANGUAGE_TO_INDIC.get(source_language, source_language)
        target_code = LANGUAGE_TO_INDIC.get(target_language, target_language)
        try:
            output = translator(text, src_lang=source_code, tgt_lang=target_code, max_length=512)
        except TypeError:
            output = translator(text, max_length=512)
        return str(output[0]["translation_text"])


def external_translation_provider(text: str, source_language: str, target_language: str) -> str:
    """Translate through the optional deep-translator fallback provider."""

    from deep_translator import GoogleTranslator

    source_code = LANGUAGE_TO_EXTERNAL.get(source_language, source_language)
    target_code = LANGUAGE_TO_EXTERNAL.get(target_language, target_language)
    result = GoogleTranslator(source=source_code, target=target_code).translate(text)
    if not result:
        raise RuntimeError("External translation provider returned an empty result")
    return str(result)


class TranslationService:
    """Cached translation service with injectable providers for testing."""

    def __init__(
        self,
        settings: Settings | None = None,
        local_provider: TranslationProvider | None = None,
        external_provider: TranslationProvider | None = None,
        cache_size: int = 2048,
    ) -> None:
        self.settings = settings or get_settings()
        self._local_provider = local_provider
        self._external_provider = external_provider
        self._cache_size = cache_size
        self._cache: OrderedDict[tuple[str, str, str], TranslationResult] = OrderedDict()
        self._cache_lock = RLock()

    def _get_local_provider(self) -> TranslationProvider | None:
        """Create the local provider only when translation is enabled."""

        if not self.settings.enable_translation:
            return None
        if self._local_provider is None:
            self._local_provider = IndicTrans2Provider(self.settings.translation_model)
        return self._local_provider

    def _get_external_provider(self) -> TranslationProvider | None:
        """Return the external fallback only when explicitly enabled."""

        if not self.settings.translation_external_fallback:
            return None
        if self._external_provider is None:
            self._external_provider = external_translation_provider
        return self._external_provider

    def _cache_get(self, key: tuple[str, str, str]) -> TranslationResult | None:
        """Read and refresh one cached translation."""

        with self._cache_lock:
            result = self._cache.get(key)
            if result is not None:
                self._cache.move_to_end(key)
            return result

    def _cache_put(self, key: tuple[str, str, str], result: TranslationResult) -> None:
        """Store one translation and evict the least recently used entry."""

        with self._cache_lock:
            self._cache[key] = result
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)

    def translate(self, text: str, source_language: str, target_language: str = "en") -> TranslationResult:
        """Translate text, falling back safely when a provider is unavailable."""

        normalized_text = " ".join((text or "").split())
        source = source_language.strip().lower()
        target = target_language.strip().lower()
        if not normalized_text:
            return TranslationResult("", source, target, "empty", True)

        key = (normalized_text, source, target)
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        if source == target:
            result = TranslationResult(normalized_text, source, target, "identity", False)
            self._cache_put(key, result)
            return result

        providers = (
            ("indictrans2", self._get_local_provider()),
            ("external", self._get_external_provider()),
        )
        for provider_name, provider in providers:
            if provider is None:
                continue
            try:
                translated = provider(normalized_text, source, target).strip()
                if translated:
                    result = TranslationResult(translated, source, target, provider_name, False)
                    self._cache_put(key, result)
                    return result
            except Exception:
                logger.exception("Translation provider failed: %s", provider_name)

        result = TranslationResult(normalized_text, source, target, "original_text_fallback", True)
        self._cache_put(key, result)
        return result

    def translate_for_officer(self, text: str, source_language: str) -> TranslationResult:
        """Translate a citizen complaint into the officer-facing English summary."""

        return self.translate(text, source_language, "en")


_service: TranslationService | None = None


def get_translation_service() -> TranslationService:
    """Return the process-wide translation service."""

    global _service
    if _service is None:
        _service = TranslationService()
    return _service


def translate_text(text: str, source_language: str, target_language: str = "en") -> TranslationResult:
    """Translate through the process-wide cached service."""

    return get_translation_service().translate(text, source_language, target_language)
