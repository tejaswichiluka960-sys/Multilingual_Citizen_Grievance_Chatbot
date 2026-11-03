"""Localized citizen registration, login and browser chat pages."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.auth import (
    authenticate_user,
    create_session,
    get_user_from_session,
    register_user,
)
from app.services.localization import get_localization_service, localized_message

router = APIRouter(tags=["web"])
CHAT_PAGE = Path(__file__).with_name("chat.html")
SUPPORTED_LANGUAGES = ("en", "hi", "te")
SESSION_COOKIE = "citizen_session"


def _language(value: str | None) -> str:
    """Resolve a requested language to one supported citizen locale."""

    locale = get_localization_service().resolve_locale(value)
    return locale if locale in SUPPORTED_LANGUAGES else "en"


def _page_shell(content: str, language: str, title: str | None = None) -> HTMLResponse:
    """Render a small shared localized authentication page."""

    page_title = title or localized_message("app_title", language)
    document = f"""<!doctype html>
<html lang="{language}">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{page_title}</title>
<style>
:root {{ font-family: Segoe UI, Arial, sans-serif; color: #172033; }}
body {{ margin: 0; background: #f5f7fb; }}
header {{ background: #d90445; color: white; padding: 22px 6vw; }}
main {{ max-width: 520px; margin: 30px auto; padding: 0 16px 40px; }}
.panel {{ background: white; border-radius: 14px; box-shadow: 0 3px 14px #17203318; padding: 24px; }}
label {{ display: grid; gap: 6px; margin: 14px 0; font-weight: 600; }}
input, button {{ border: 1px solid #c9d0dc; border-radius: 8px; padding: 10px; font: inherit; }}
button {{ background: #d90445; color: white; border: 0; cursor: pointer; font-weight: 700; width: 100%; }}
a {{ color: #334e8c; }} .error {{ color: #b00020; background: #fff0f0; padding: 10px; border-radius: 8px; }}
</style></head><body>{content}</body></html>"""
    return HTMLResponse(document)


def _set_citizen_cookies(response: RedirectResponse, request: Request, token: str, language: str) -> None:
    """Set the session and selected-language cookies safely."""

    secure = request.url.scheme == "https"
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=604800)
    response.set_cookie("preferred_language", language, httponly=False, samesite="lax", secure=secure, max_age=31536000)


def _language_links() -> str:
    """Return the initial language selection buttons."""

    labels = {"en": "English", "hi": "हिंदी", "te": "తెలుగు"}
    return "".join(
        f'<a href="/register?language={code}" style="display:block;margin:10px 0;padding:12px;background:#d90445;color:white;text-decoration:none;border-radius:8px;text-align:center">{label}</a>'
        for code, label in labels.items()
    )


@router.get("/welcome", response_class=HTMLResponse, include_in_schema=False)
def welcome_page() -> HTMLResponse:
    """Show language selection before registration or login."""

    content = f"""<header><h1>{localized_message('app_title', 'en')}</h1></header>
<main><section class="panel"><h2>{localized_message('select_language', 'en')}</h2>{_language_links()}</section></main>"""
    return _page_shell(content, "en")


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_page(language: str | None = None, error: str | None = None) -> HTMLResponse:
    """Render the localized citizen registration form."""

    locale = _language(language)
    error_html = f'<p class="error">{error}</p>' if error else ""
    content = f"""<header><h1>{localized_message('app_title', locale)}</h1><p>{localized_message('register', locale)}</p></header>
<main><section class="panel">{error_html}<form method="post" action="/register">
<input type="hidden" name="language" value="{locale}" />
<label>{localized_message('full_name', locale)}<input name="name" maxlength="150" required /></label>
<label>{localized_message('username', locale)}<input name="username" minlength="3" maxlength="100" autocomplete="username" required /></label>
<label>{localized_message('password', locale)}<input type="password" name="password" minlength="8" maxlength="128" autocomplete="new-password" required /></label>
<label>{localized_message('confirm_password', locale)}<input type="password" name="confirm_password" minlength="8" maxlength="128" autocomplete="new-password" required /></label>
<button type="submit">{localized_message('create_account', locale)}</button></form>
<p><a href="/login?language={locale}">{localized_message('already_have_account', locale)}</a></p></section></main>"""
    return _page_shell(content, locale)


@router.post("/register", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def register_submit(
    request: Request,
    name: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    language: str = Form(default="en"),
    db: Session = Depends(get_db),  # noqa: B008
) -> RedirectResponse | HTMLResponse:
    """Create a citizen account and sign the user in."""

    locale = _language(language)
    if password != confirm_password:
        return register_page(locale, localized_message("password_mismatch", locale))
    try:
        user = register_user(db, username=username, password=password, name=name, language=locale)
    except ValueError as exc:
        return register_page(locale, str(exc))
    response = RedirectResponse(url="/chat", status_code=303)
    _set_citizen_cookies(response, request, create_session(db, user.id), locale)
    return response


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(language: str | None = None, error: str | None = None) -> HTMLResponse:
    """Render the localized citizen login form."""

    locale = _language(language)
    error_html = f'<p class="error">{error}</p>' if error else ""
    content = f"""<header><h1>{localized_message('app_title', locale)}</h1><p>{localized_message('login', locale)}</p></header>
<main><section class="panel">{error_html}<form method="post" action="/login">
<input type="hidden" name="language" value="{locale}" />
<label>{localized_message('username', locale)}<input name="username" autocomplete="username" required /></label>
<label>{localized_message('password', locale)}<input type="password" name="password" autocomplete="current-password" required /></label>
<button type="submit">{localized_message('login', locale)}</button></form>
<p><a href="/register?language={locale}">{localized_message('no_account', locale)}</a></p></section></main>"""
    return _page_shell(content, locale)


@router.post("/login", response_class=HTMLResponse, response_model=None, include_in_schema=False)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    language: str = Form(default="en"),
    db: Session = Depends(get_db),  # noqa: B008
) -> RedirectResponse | HTMLResponse:
    """Authenticate a citizen and create a browser session."""

    locale = _language(language)
    user = authenticate_user(db, username=username, password=password)
    if user is None:
        return login_page(locale, localized_message("invalid_credentials", locale))
    response = RedirectResponse(url="/chat", status_code=303)
    _set_citizen_cookies(response, request, create_session(db, user.id), user.preferred_lang)
    return response


@router.get("/logout", include_in_schema=False)
def logout() -> RedirectResponse:
    """Clear the browser session."""

    response = RedirectResponse(url="/welcome", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("/chat", response_class=HTMLResponse, include_in_schema=False)
def chat_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:  # noqa: B008
    """Serve the localized chat page only to registered citizens."""

    user = get_user_from_session(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        return RedirectResponse(url="/welcome", status_code=303)
    locale = _language(user.preferred_lang)
    texts = {
        key: localized_message(key, locale)
        for key in (
            "app_title", "app_subtitle", "logout", "status_hint", "send", "record_voice",
            "stop_recording", "transcribing", "microphone_required", "welcome_chat",
            "describe_complaint", "voice_transcript_ready", "ticket_label",
        )
    }
    texts["language_name"] = localized_message(f"language_name_{locale}", locale)
    document = CHAT_PAGE.read_text(encoding="utf-8")
    document = document.replace("__LANGUAGE__", locale).replace("__UI_TEXT__", json.dumps(texts, ensure_ascii=False))
    return HTMLResponse(document)
