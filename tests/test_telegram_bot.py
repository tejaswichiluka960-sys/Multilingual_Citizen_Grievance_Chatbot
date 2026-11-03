"""Tests for the Telegram bot foundation without contacting Telegram."""

import pytest

from app.bot.telegram_bot import (
    LANGUAGE_CALLBACKS,
    build_telegram_application,
    get_user_language,
    language_keyboard,
)
from app.config import get_settings


def test_language_keyboard_contains_supported_callback_values() -> None:
    keyboard = language_keyboard()

    callbacks = {button.callback_data for row in keyboard.inline_keyboard for button in row}
    assert callbacks == set(LANGUAGE_CALLBACKS)


def test_user_language_defaults_safely() -> None:
    assert get_user_language(None) == "en"
    assert get_user_language({"language": "hi"}) == "hi"
    assert get_user_language({"language": "unsupported"}) == "en"


def test_application_registers_foundation_handlers() -> None:
    application = build_telegram_application("123456:TEST_TOKEN")

    assert len(application.handlers[0]) == 7
    assert {handler.commands for handler in application.handlers[0][:3]} == {
        frozenset({"start"}),
        frozenset({"help"}),
        frozenset({"cancel"}),
    }
    assert application.handlers[0][4].pattern.pattern == r"^language:(en|hi|te)$"
    assert application.handlers[0][5].pattern.pattern == r"^department:[A-Z]+$"


def test_application_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")

    try:
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            build_telegram_application()
    finally:
        get_settings.cache_clear()
