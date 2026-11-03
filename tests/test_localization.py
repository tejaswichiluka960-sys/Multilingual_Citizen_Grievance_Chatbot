"""Tests for localized message resolution and deterministic fallbacks."""

from pathlib import Path

from app.services.localization import LocalizationService


def test_bundled_catalogs_and_language_aliases_are_available() -> None:
    service = LocalizationService()

    assert service.available_locales == ("en", "hi", "te")
    assert service.resolve_locale("hinglish") == "hi"
    assert service.resolve_locale("tenglish") == "te"
    assert service.resolve_locale("unsupported") == "en"
    assert "स्वागत" in service.message("welcome", "hi")
    assert "స్వాగతం" in service.message("welcome", "te")


def test_parameterized_message_is_rendered_in_selected_locale() -> None:
    service = LocalizationService()

    result = service.message(
        "ticket_created_with_id",
        "hi",
        ticket_code="GRV-0001",
        department="जल विभाग",
    )

    assert "GRV-0001" in result
    assert "जल विभाग" in result


def test_missing_key_and_missing_catalog_use_safe_fallbacks(tmp_path: Path) -> None:
    service = LocalizationService(tmp_path)

    assert service.message("unknown_key", "te") == "unknown_key"
    assert service.message("welcome", "te") == "welcome"


def test_missing_localized_key_falls_back_to_english(tmp_path: Path) -> None:
    (tmp_path / "en.json").write_text('{"only_english": "English {value}"}', encoding="utf-8")
    (tmp_path / "hi.json").write_text("{}", encoding="utf-8")
    service = LocalizationService(tmp_path)

    assert service.message("only_english", "hi", value="text") == "English text"
