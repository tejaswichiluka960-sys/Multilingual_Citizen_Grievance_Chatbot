"""Smoke tests for the initial FastAPI application."""

from app.config import get_settings
from app.main import app, health, root
from app.web.routes import login_page, register_page, welcome_page


def test_root_returns_service_status() -> None:
    response = root()

    assert response["status"] == "ok"


def test_health_returns_ok() -> None:
    response = health()

    assert response.status == "ok"
    assert response.database_status == "ok"


def test_environment_settings_are_available() -> None:
    settings = get_settings()

    assert settings.database_url.startswith(("sqlite", "postgresql"))
    assert "http://localhost:8000" in settings.cors_origin_list


def test_cors_middleware_is_configured() -> None:
    middleware_names = [middleware.cls.__name__ for middleware in app.user_middleware]

    assert "CORSMiddleware" in middleware_names
    assert "TrustedHostMiddleware" in middleware_names


def test_auth_pages_use_civic_calm_issue_background() -> None:
    """The language, registration and login pages share the selected theme."""

    for page in (welcome_page(), register_page("en"), login_page("en")):
        body = page.body.decode()
        assert 'class="auth-backdrop"' in body
        assert "Water & drainage" in body
        assert "Electricity" in body
