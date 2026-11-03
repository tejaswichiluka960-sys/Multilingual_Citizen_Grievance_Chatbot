"""FastAPI endpoint for the browser chat fallback."""

import re
from threading import RLock
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Ticket
from app.schemas import ChatChoice, ChatRequest, ChatResponse
from app.services import tickets as ticket_service
from app.services.intake import (
    PreparedComplaint,
    create_prepared_ticket,
    prepare_complaint,
)
from app.services.localization import get_localization_service, localized_message

router = APIRouter(tags=["chat"])

DEPARTMENT_CODES = (
    "WATER",
    "POWER",
    "ROADS",
    "SANITATION",
    "POLICE",
    "HEALTH",
    "EDUCATION",
    "TRANSPORT",
    "REVENUE",
    "OTHER",
)
TICKET_CODE_PATTERN = re.compile(r"^GRV-\d{4}-\d{6}$", re.IGNORECASE)
_pending_complaints: dict[str, PreparedComplaint] = {}
_pending_lock = RLock()


def _session_id(value: str | None) -> str:
    """Return a stable client session ID or create one for a new browser."""

    return value.strip() if value else f"web-{uuid4().hex}"


def _locale(language: str) -> str:
    """Resolve a request language to a bundled response locale."""

    return get_localization_service().resolve_locale(language)


def _department_choices(language: str) -> list[ChatChoice]:
    """Return localized department choices for the browser."""

    return [
        ChatChoice(
            code=code,
            label=localized_message(f"department_{code.lower()}", language),
        )
        for code in DEPARTMENT_CODES
    ]


def _ticket_reply(ticket: Ticket, language: str, session_id: str) -> ChatResponse:
    """Build a browser response after ticket creation."""

    department_code = ticket.department.code if ticket.department else "OTHER"
    return ChatResponse(
        session_id=session_id,
        language=language,
        reply=localized_message(
            "ticket_created_with_id",
            language,
            ticket_code=ticket.ticket_code,
            department=localized_message(f"department_{department_code.lower()}", language),
        ),
        ticket_code=ticket.ticket_code,
        department_code=department_code,
        status=ticket.status,
    )


def _status_response(db: Session, session_id: str, language: str, code: str) -> ChatResponse:
    """Return a localized ticket status response."""

    normalized = code.strip().upper()
    ticket = ticket_service.get_ticket_by_code(db, normalized) if TICKET_CODE_PATTERN.fullmatch(normalized) else None
    if ticket is None:
        return ChatResponse(
            session_id=session_id,
            language=language,
            reply=localized_message("status_not_found", language),
        )
    return ChatResponse(
        session_id=session_id,
        language=language,
        reply=localized_message(
            "status_update",
            language,
            ticket_code=normalized,
            status=localized_message(f"status_{ticket.status.lower()}", language),
        ),
        ticket_code=ticket.ticket_code,
        department_code=ticket.department.code if ticket.department else None,
        status=ticket.status,
    )


@router.post("/chat", response_model=ChatResponse)
def chat_route(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:  # noqa: B008
    """Process one browser message through the shared complaint workflow."""

    session_id = _session_id(payload.session_id)
    language = _locale(payload.language)
    message = payload.message.strip()
    if message.lower().startswith("/status"):
        code = message[7:].strip()
        if not code:
            return ChatResponse(
                session_id=session_id,
                language=language,
                reply=localized_message("status_prompt", language),
            )
        return _status_response(db, session_id, language, code)

    with _pending_lock:
        pending = _pending_complaints.get(session_id)
    if payload.department_code:
        if pending is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No complaint needs clarification")
        department_code = payload.department_code.strip().upper()
        if department_code not in DEPARTMENT_CODES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown department")
        try:
            ticket = create_prepared_ticket(
                db,
                prepared=pending,
                user_id=None,
                department_code=department_code,
                actor="web-chat",
                source_channel="web",
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        with _pending_lock:
            _pending_complaints.pop(session_id, None)
        return _ticket_reply(ticket, language, session_id)

    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")
    try:
        prepared = prepare_complaint(message, language)
        if prepared.needs_clarification:
            with _pending_lock:
                _pending_complaints[session_id] = prepared
            return ChatResponse(
                session_id=session_id,
                language=language,
                reply=(
                    f"{localized_message('clarification_prompt', language)}\n"
                    f"{localized_message('department_question', language)}"
                ),
                choices=_department_choices(language),
            )
        ticket = create_prepared_ticket(
            db,
            prepared=prepared,
            user_id=None,
            actor="web-chat",
            source_channel="web",
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ticket_reply(ticket, language, session_id)
