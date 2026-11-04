"""Localized citizen registration, login and browser chat pages."""

import html
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import tickets as ticket_service
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
:root {{ font-family: Segoe UI, Arial, sans-serif; color: #183247; }}
* {{ box-sizing: border-box; }}
body {{ position: relative; min-height: 100vh; margin: 0; overflow-x: hidden; background: linear-gradient(135deg, #e8f7f8, #f4f8fb); }}
body::before, body::after {{ position: fixed; z-index: 0; border-radius: 50%; content: ""; pointer-events: none; }}
body::before {{ top: -120px; right: -90px; width: 320px; height: 320px; background: #8bd8d633; }}
body::after {{ bottom: -150px; left: -110px; width: 360px; height: 360px; background: #f5c54222; }}
.auth-backdrop {{ position: fixed; z-index: 0; inset: 0; display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; align-content: end; padding: 0 5vw 24px; pointer-events: none; opacity: .22; }}
.auth-backdrop span {{ min-height: 104px; padding: 14px; border-radius: 18px; color: white; font-size: 12px; font-weight: 700; box-shadow: 0 16px 30px #244f5f1c; }}
.auth-backdrop span small {{ display: block; margin-top: 7px; font-weight: 400; opacity: .9; }}
.auth-water {{ background: linear-gradient(155deg, #0c7f9a, #52c5c4); }}
.auth-power {{ background: linear-gradient(155deg, #7d5b10, #e9ae33); }}
.auth-roads {{ background: linear-gradient(155deg, #394655, #8292a0); }}
.auth-public {{ background: linear-gradient(155deg, #a84b64, #e98c9c); }}
header, main {{ position: relative; z-index: 1; }}
header {{ background: linear-gradient(135deg, #167c80, #19566f); border-bottom: 5px solid #f5c542; color: white; padding: 22px 6vw; box-shadow: 0 8px 24px #244f5f1c; }}
header h1 {{ margin: 0 0 5px; }}
header p {{ margin: 0; color: #d8f1ef; }}
main {{ max-width: 520px; margin: 30px auto; padding: 0 16px 40px; }}
.panel {{ background: #fffffff2; border: 1px solid #d9e7e9; border-radius: 20px; box-shadow: 0 14px 35px #244f5f1a; padding: 24px; backdrop-filter: blur(8px); }}
label {{ display: grid; gap: 6px; margin: 14px 0; font-weight: 600; }}
input, button {{ border: 1px solid #d5e2e6; border-radius: 11px; padding: 11px; font: inherit; }}
input:focus {{ outline: 3px solid #8bd8d655; border-color: #167c80; }}
button {{ background: #167c80; color: white; border: 0; cursor: pointer; font-weight: 700; width: 100%; }}
button:hover {{ background: #126b6e; }}
a {{ color: #167c80; }} .error {{ color: #b42318; background: #fff1ef; padding: 10px; border-radius: 8px; }}
@media (max-width: 700px) {{ .auth-backdrop {{ grid-template-columns: 1fr 1fr; align-content: end; padding: 0 16px 12px; }} .auth-backdrop span {{ min-height: 72px; }} }}
</style></head><body>
<div class="auth-backdrop" aria-hidden="true">
  <span class="auth-water">Water & drainage<small>Leaks · supply</small></span>
  <span class="auth-power">Electricity<small>Outage · street lights</small></span>
  <span class="auth-roads">Roads & transport<small>Potholes · buses</small></span>
  <span class="auth-public">Health & sanitation<small>Waste · clinics</small></span>
</div>
{content}</body></html>"""
    return HTMLResponse(document)


def _citizen_page_shell(content: str, language: str, title: str) -> HTMLResponse:
    """Render a localized citizen page with consistent navigation controls."""

    nav = f"""
    <nav class="page-nav" aria-label="Citizen navigation">
      <a href="/chat">{html.escape(localized_message("home", language))}</a>
      <a href="/my-tickets">{html.escape(localized_message("my_tickets", language))}</a>
      <a href="/profile">{html.escape(localized_message("profile", language))}</a>
      <button type="button" onclick="if (history.length > 1) history.back(); else window.location='/chat';">{html.escape(localized_message("back", language))}</button>
      <a href="/logout">{html.escape(localized_message("logout", language))}</a>
    </nav>"""
    document = f"""<!doctype html>
<html lang="{language}">
<head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(title)}</title>
<style>
:root {{ font-family: Segoe UI, Arial, sans-serif; color: #183b56; }}
body {{ margin: 0; background: #eef3f7; }}
header {{ background: #12355b; border-bottom: 5px solid #f5c542; color: white; padding: 22px 6vw; }}
main {{ max-width: 980px; margin: 24px auto; padding: 0 16px 40px; }}
.page-nav {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }}
.page-nav a, .page-nav button {{ border: 1px solid #bdcbd6; border-radius: 7px; padding: 9px 12px; background: white; color: #12355b; text-decoration: none; font: inherit; cursor: pointer; }}
.page-nav a:last-child {{ background: #00695c; border-color: #00695c; color: white; }}
.panel, .ticket-card {{ background: white; border: 1px solid #d8e2ea; border-radius: 10px; box-shadow: 0 6px 22px #183b5618; padding: 20px; margin-bottom: 14px; }}
label {{ display: grid; gap: 6px; font-weight: 700; }}
input, button {{ border: 1px solid #bdcbd6; border-radius: 7px; padding: 11px; font: inherit; }}
.search-form {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }}
.search-form label {{ flex: 1; min-width: 240px; }}
.search-form button {{ background: #00695c; border: 0; color: white; font-weight: 700; cursor: pointer; }}
.ticket-header {{ display: flex; justify-content: space-between; gap: 12px; }}
.status {{ color: #00695c; font-weight: 700; }}
.status-tracking {{ margin-top: 16px; padding-top: 14px; border-top: 1px solid #e1e9ef; }}
.status-tracking h3 {{ margin: 0 0 10px; color: #12355b; font-size: 1rem; }}
.status-badge {{ display: inline-block; padding: 5px 9px; border-radius: 999px; background: #e5f4ef; color: #00695c; font-weight: 700; font-size: .85rem; }}
.timeline {{ list-style: none; margin: 12px 0 0; padding: 0 0 0 20px; border-left: 2px solid #cbd9e3; }}
.timeline li {{ position: relative; padding: 0 0 13px 14px; color: #526b82; }}
.timeline li::before {{ content: ""; position: absolute; width: 10px; height: 10px; border-radius: 50%; background: #bdcbd6; border: 2px solid white; left: -27px; top: 2px; }}
.timeline li.current {{ color: #183b56; font-weight: 700; }}
.timeline li.current::before {{ background: #00695c; box-shadow: 0 0 0 3px #d7eee9; }}
.timeline small {{ display: block; font-weight: 400; color: #71879a; margin-top: 3px; }}
dl {{ display: grid; grid-template-columns: minmax(130px, 220px) 1fr; gap: 12px; }}
dt {{ color: #526b82; font-weight: 700; }}
dd {{ margin: 0; }}
@media (max-width: 600px) {{ dl {{ grid-template-columns: 1fr; gap: 4px; }} }}
</style></head><body>
<header><h1>{html.escape(localized_message("app_title", language))}</h1><p>{html.escape(localized_message("app_subtitle", language))}</p></header>
<main>{nav}{content}</main></body></html>"""
    return HTMLResponse(document)


def _set_citizen_cookies(response: RedirectResponse, request: Request, token: str, language: str) -> None:
    """Set the session and selected-language cookies safely."""

    secure = request.url.scheme == "https"
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=604800)
    response.set_cookie("preferred_language", language, httponly=False, samesite="lax", secure=secure, max_age=31536000)


def _set_language_cookie(response: RedirectResponse, request: Request, language: str) -> None:
    """Remember the selected language before the user logs in."""

    response.set_cookie(
        "preferred_language",
        language,
        httponly=False,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=31536000,
    )


def _language_links() -> str:
    """Return the initial language selection buttons."""

    labels = {"en": "English", "hi": "हिंदी", "te": "తెలుగు"}
    return "".join(
        f'<a href="/register?language={code}" style="display:block;margin:10px 0;padding:12px;background:#0f766e;color:white;text-decoration:none;border-radius:10px;text-align:center">{label}</a>'
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
        register_user(db, username=username, password=password, name=name, language=locale)
    except ValueError as exc:
        return register_page(locale, str(exc))
    response = RedirectResponse(url=f"/login?language={locale}&registered=true", status_code=303)
    _set_language_cookie(response, request, locale)
    return response


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(
    language: str | None = None,
    error: str | None = None,
    registered: bool = False,
) -> HTMLResponse:
    """Render the localized citizen login form."""

    locale = _language(language)
    error_html = f'<p class="error">{error}</p>' if error else ""
    notice_html = f'<p>{localized_message("registration_success", locale)}</p>' if registered else ""
    content = f"""<header><h1>{localized_message('app_title', locale)}</h1><p>{localized_message('login', locale)}</p></header>
<main><section class="panel">{error_html}<form method="post" action="/login">
{notice_html}
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


@router.get("/my-tickets", response_class=HTMLResponse, include_in_schema=False)
def my_tickets_page(
    request: Request,
    ticket_code: str | None = Query(default=None, max_length=32),
    db: Session = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Show and search tickets belonging only to the logged-in citizen."""

    user = get_user_from_session(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        return RedirectResponse(url="/welcome", status_code=303)
    locale = _language(user.preferred_lang)
    ticket_filter = ticket_code if isinstance(ticket_code, str) else None
    tickets = ticket_service.list_tickets_by_user(db, user_id=user.id, ticket_code=ticket_filter)
    cards: list[str] = []
    for ticket in tickets:
        department_code = ticket.department.code if ticket.department else "OTHER"
        department = localized_message(f"department_{department_code.lower()}", locale)
        status_key = "status_routed" if ticket.status == "ASSIGNED" else f"status_{ticket.status.lower()}"
        status_label = localized_message(status_key, locale)
        ticket_label = localized_message(
            "ticket_label",
            locale,
            ticket_code=ticket.ticket_code,
            department=department,
            intent=ticket.intent or "-",
        )
        details = localized_message(
            "ticket_details",
            locale,
            address=ticket.location_text or "-",
            incident_date=ticket.incident_date.isoformat() if ticket.incident_date else "-",
            incident_time=ticket.incident_time.strftime("%H:%M") if ticket.incident_time else "-",
        )
        events = [
            (
                f'<li>{html.escape(localized_message("status_created", locale))}'
                f'<small>{html.escape(ticket.created_at.strftime("%d %b %Y, %H:%M UTC"))}</small></li>'
            )
        ]
        for index, event in enumerate(ticket.events):
            event_key = "status_routed" if event.new_status == "ASSIGNED" else f"status_{event.new_status.lower()}"
            event_status = localized_message(event_key, locale)
            event_note = f" — {event.note}" if event.note else ""
            if event.new_status == "ASSIGNED" and ticket.department is not None:
                department_name = localized_message(f"department_{ticket.department.code.lower()}", locale)
                event_note = f" — {localized_message('routed_to_department', locale, department=department_name)}"
            timestamp = event.created_at.strftime("%d %b %Y, %H:%M UTC")
            current_class = " current" if index == len(ticket.events) - 1 else ""
            events.append(
                f'<li class="{current_class.strip()}">{html.escape(event_status + event_note)}'
                f'<small>{html.escape(timestamp)}</small></li>'
            )
        timeline = "".join(events) or f'<li>{html.escape(localized_message("no_status_events", locale))}</li>'
        expected_text = localized_message("expected_resolution", locale)
        if ticket.sla_due_at:
            expected_text = f'{expected_text}: {ticket.sla_due_at.strftime("%d %b %Y, %H:%M UTC")}'
        cards.append(
            f'<article class="ticket-card"><div class="ticket-header"><strong>{html.escape(ticket_label)}</strong>'
            f'<span class="status">{html.escape(status_label)}</span></div>'
            f'<p>{html.escape(details)}</p><p>{html.escape(ticket.original_text)}</p>'
            f'<section class="status-tracking"><h3>{html.escape(localized_message("status_tracking", locale))}</h3>'
            f'<span class="status-badge">{html.escape(localized_message("current_status", locale))}: {html.escape(status_label)}</span>'
            f'<p>{html.escape(expected_text)}</p>'
            f'<ol class="timeline">{timeline}</ol></section></article>'
        )
    ticket_cards = "".join(cards) or f'<section class="panel"><p>{html.escape(localized_message("no_tickets", locale))}</p></section>'
    search_value = html.escape(ticket_filter or "", quote=True)
    content = f"""
    <section class="panel">
      <h2>{html.escape(localized_message("my_tickets", locale))}</h2>
      <form class="search-form" method="get" action="/my-tickets">
        <label>{html.escape(localized_message("search_tickets", locale))}
          <input name="ticket_code" value="{search_value}" maxlength="32" placeholder="{html.escape(localized_message("ticket_search_placeholder", locale), quote=True)}" />
        </label>
        <button type="submit">{html.escape(localized_message("search", locale))}</button>
      </form>
    </section>
    {ticket_cards}
    """
    return _citizen_page_shell(content, locale, localized_message("my_tickets", locale))


@router.get("/profile", response_class=HTMLResponse, include_in_schema=False)
def profile_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:  # noqa: B008
    """Show the logged-in citizen's account information."""

    user = get_user_from_session(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        return RedirectResponse(url="/welcome", status_code=303)
    locale = _language(user.preferred_lang)
    content = f"""
    <section class="panel">
      <h2>{html.escape(localized_message("profile", locale))}</h2>
      <dl>
        <dt>{html.escape(localized_message("full_name", locale))}</dt><dd>{html.escape(user.name or "-")}</dd>
        <dt>{html.escape(localized_message("username", locale))}</dt><dd>{html.escape(user.username or "-")}</dd>
        <dt>{html.escape(localized_message("preferred_language", locale))}</dt><dd>{html.escape(localized_message(f"language_name_{locale}", locale))}</dd>
      </dl>
    </section>
    """
    return _citizen_page_shell(content, locale, localized_message("profile", locale))


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
            "describe_complaint", "complaint_details", "complaint_label", "required_hint", "address", "address_placeholder", "address_required", "incident_date",
            "incident_time", "ticket_details", "voice_transcript_ready", "ticket_label", "sending", "sent",
            "failed_to_send", "side_claim", "step_complaint", "step_department", "step_track", "online",
            "home", "my_tickets", "profile", "back", "view_my_tickets", "status_tracking",
            "expected_resolution", "no_status_events",
        )
    }
    texts["language_name"] = localized_message(f"language_name_{locale}", locale)
    document = CHAT_PAGE.read_text(encoding="utf-8")
    document = document.replace("__LANGUAGE__", locale).replace("__UI_TEXT__", json.dumps(texts, ensure_ascii=False))
    return HTMLResponse(document)
