"""Security configuration and authentication tests."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from pydantic import ValidationError

from app.config import Settings
from app.security import require_admin


def test_production_rejects_default_security_values() -> None:
    """Production cannot start with debug mode and demo credentials."""

    with pytest.raises(ValidationError):
        Settings(app_env="production", debug=True, secret_key="change-me", admin_password=None)


def test_admin_credentials_are_checked(monkeypatch) -> None:
    """Configured officer credentials are required and compared safely."""

    monkeypatch.setenv("ADMIN_USERNAME", "officer")
    monkeypatch.setenv("ADMIN_PASSWORD", "local-test-password")
    from app.config import get_settings

    get_settings.cache_clear()
    assert require_admin(HTTPBasicCredentials(username="officer", password="local-test-password")) == "officer"
    with pytest.raises(HTTPException):
        require_admin(HTTPBasicCredentials(username="officer", password="wrong"))
    get_settings.cache_clear()
