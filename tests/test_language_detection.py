"""Tests for multilingual language and code-mixing detection."""

from app.services.language_detection import (
    LANGUAGE_ENGLISH,
    LANGUAGE_HINDI,
    LANGUAGE_HINGLISH,
    LANGUAGE_MIXED,
    LANGUAGE_TELUGU,
    LANGUAGE_TENGLISH,
    LANGUAGE_UNKNOWN,
    detect_language,
)


def test_detects_english_roman_text() -> None:
    result = detect_language("There is no water supply near my street.")

    assert result.language == LANGUAGE_ENGLISH
    assert result.script == "latin"
    assert result.is_code_mixed is False
    assert result.confidence >= 0.8


def test_detects_hindi_devanagari() -> None:
    result = detect_language("मेरे इलाके में पानी नहीं आ रहा है")

    assert result.language == LANGUAGE_HINDI
    assert result.script == "devanagari"
    assert result.is_code_mixed is False
    assert result.needs_confirmation is False


def test_detects_telugu_script() -> None:
    result = detect_language("మా వీధిలో నీటి సరఫరా లేదు")

    assert result.language == LANGUAGE_TELUGU
    assert result.script == "telugu"
    assert result.is_code_mixed is False
    assert result.needs_confirmation is False


def test_detects_hinglish() -> None:
    result = detect_language("Mere area mein pani nahi aa raha hai")

    assert result.language == LANGUAGE_HINGLISH
    assert result.is_code_mixed is True
    assert any(item.startswith("hinglish:") for item in result.evidence)


def test_detects_tenglish() -> None:
    result = detect_language("Ma area lo neellu levu, please cheyyandi")

    assert result.language == LANGUAGE_TENGLISH
    assert result.is_code_mixed is True
    assert any(item.startswith("tenglish:") for item in result.evidence)


def test_marks_indic_and_english_script_mixing() -> None:
    result = detect_language("मेरे ward में water problem है")

    assert result.language == LANGUAGE_HINDI
    assert result.script == "devanagari+latin"
    assert result.is_code_mixed is True


def test_marks_multiple_indic_scripts_as_mixed() -> None:
    result = detect_language("నీరు और पानी चाहिए")

    assert result.language == LANGUAGE_MIXED
    assert result.is_code_mixed is True
    assert result.confidence >= 0.9


def test_empty_emoji_and_unknown_roman_text_need_confirmation() -> None:
    for text in ("", "🙂👍", "xyz qwerty blorp"):
        result = detect_language(text)

        assert result.language == LANGUAGE_UNKNOWN
        assert result.needs_confirmation is True
