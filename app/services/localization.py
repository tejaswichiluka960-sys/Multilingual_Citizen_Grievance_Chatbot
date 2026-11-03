"""Localized message catalog service for citizen-facing responses."""

import json
import logging
from pathlib import Path
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "hi", "te")
LANGUAGE_TO_LOCALE = {
    "en": "en",
    "hi": "hi",
    "te": "te",
    "hinglish": "hi",
    "tenglish": "te",
    "mixed": "en",
    "unknown": "en",
}
CATALOG_DIR = Path(__file__).resolve().parents[1] / "bot" / "i18n"


class LocalizationService:
    """Load and resolve user-facing messages with deterministic fallbacks."""

    def __init__(self, catalog_dir: Path | str = CATALOG_DIR) -> None:
        self.catalog_dir = Path(catalog_dir)
        self._catalogs: dict[str, dict[str, str]] = {}
        self._lock = RLock()

    @property
    def available_locales(self) -> tuple[str, ...]:
        """Return the locales supported by the bundled catalogs."""

        return SUPPORTED_LOCALES

    def resolve_locale(self, language: str | None) -> str:
        """Map a detected language to a supported response locale."""

        normalized = (language or DEFAULT_LOCALE).strip().lower()
        return LANGUAGE_TO_LOCALE.get(normalized, DEFAULT_LOCALE)

    def _load_catalog(self, locale: str) -> dict[str, str]:
        """Load one catalog once and ignore malformed optional catalogs safely."""

        with self._lock:
            if locale in self._catalogs:
                return self._catalogs[locale]

            catalog_path = self.catalog_dir / f"{locale}.json"
            try:
                payload = json.loads(catalog_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise TypeError("catalog root must be an object")
                catalog = {str(key): str(value) for key, value in payload.items() if isinstance(value, str)}
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                logger.warning("Unable to load locale catalog %s: %s", catalog_path, exc)
                catalog = {}

            self._catalogs[locale] = catalog
            return catalog

    def message(self, key: str, language: str | None = DEFAULT_LOCALE, **values: Any) -> str:
        """Return a localized message, falling back by key to English."""

        locale = self.resolve_locale(language)
        localized = self._load_catalog(locale).get(key)
        english = self._load_catalog(DEFAULT_LOCALE).get(key)
        template = localized or english or key
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            logger.warning("Missing format value while rendering message key %s", key)
            return template


_service: LocalizationService | None = None


def get_localization_service() -> LocalizationService:
    """Return the process-wide localization service."""

    global _service
    if _service is None:
        _service = LocalizationService()
    return _service


def localized_message(key: str, language: str | None = DEFAULT_LOCALE, **values: Any) -> str:
    """Resolve one message through the process-wide localization service."""

    return get_localization_service().message(key, language, **values)
