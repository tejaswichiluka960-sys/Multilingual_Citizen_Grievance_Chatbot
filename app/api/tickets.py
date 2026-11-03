"""FastAPI routes for grievance ticket operations."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Department, Ticket
from app.schemas import (
    TicketCreateRequest,
    TicketEventResponse,
    TicketResponse,
    TicketStatusUpdateRequest,
)
from app.security import require_admin
from app.services import tickets as ticket_service

router = APIRouter(tags=["tickets"])


def _ticket_response(ticket: Ticket) -> TicketResponse:
    """Convert a database ticket into a stable API response."""

    department = ticket.department
    return TicketResponse(
        id=ticket.id,
        ticket_code=ticket.ticket_code,
        user_id=ticket.user_id,
        department_id=ticket.department_id,
        department_code=department.code if department else None,
        department_name=department.name if department else None,
        original_text=ticket.original_text,
        language=ticket.language,
        translated_text=ticket.translated_text,
        intent=ticket.intent,
        priority=ticket.priority,
        confidence=ticket.confidence,
        status=ticket.status,
        location_text=ticket.location_text,
        source_channel=ticket.source_channel,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        sla_due_at=ticket.sla_due_at,
        escalation_level=ticket.escalation_level,
        events=[TicketEventResponse.model_validate(event) for event in ticket.events],
    )


@router.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket_route(payload: TicketCreateRequest, db: Session = Depends(get_db)) -> TicketResponse:  # noqa: B008
    """Create a grievance ticket from validated complaint data."""

    try:
        ticket = ticket_service.create_ticket(db, **payload.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ticket_response(ticket)


@router.get("/tickets/{ticket_code}", response_model=TicketResponse)
def get_ticket_route(ticket_code: str, db: Session = Depends(get_db)) -> TicketResponse:  # noqa: B008
    """Return a ticket and its status history by public ticket code."""

    ticket = ticket_service.get_ticket_by_code(db, ticket_code)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return _ticket_response(ticket)


@router.patch("/tickets/{ticket_code}/status", response_model=TicketResponse)
def update_ticket_status_route(
    ticket_code: str,
    payload: TicketStatusUpdateRequest,
    db: Session = Depends(get_db),  # noqa: B008
    admin_user: str = Depends(require_admin),
) -> TicketResponse:
    """Update ticket status and record its event and audit entry."""

    try:
        ticket = ticket_service.update_ticket_status(
            db,
            ticket_code=ticket_code,
            new_status=payload.new_status,
            actor=payload.actor,
            note=payload.note,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ticket_response(ticket)


@router.get("/admin/tickets", response_model=list[TicketResponse])
def list_admin_tickets_route(
    department: str | None = Query(default=None, min_length=1),
    status_value: str | None = Query(default=None, alias="status", min_length=1),
    db: Session = Depends(get_db),  # noqa: B008
    admin_user: str = Depends(require_admin),
) -> list[TicketResponse]:
    """List tickets for the admin queue with optional department and status filters."""

    department_id: int | None = None
    if department is not None:
        department_record = db.scalar(
            select(Department).where(Department.code == department.strip().upper())
        )
        if department_record is None:
            return []
        department_id = department_record.id

    try:
        tickets = ticket_service.list_tickets(db, department_id=department_id, status=status_value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return [_ticket_response(ticket) for ticket in tickets]
