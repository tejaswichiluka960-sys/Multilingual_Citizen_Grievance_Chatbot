"""Business logic for creating and updating grievance tickets."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AuditLog, Department, Ticket, TicketEvent

logger = logging.getLogger(__name__)

TICKET_STATUSES = frozenset({"NEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "ESCALATED", "CLOSED", "REOPENED"})
TICKET_PRIORITIES = frozenset({"low", "medium", "high"})


def _temporary_ticket_code() -> str:
    """Return a unique temporary code used until the database assigns an ID."""

    return f"TMP-{uuid4().hex[:27]}"


def _normalize_priority(priority: str) -> str:
    """Normalize and validate a ticket priority."""

    normalized = priority.strip().lower()
    if normalized not in TICKET_PRIORITIES:
        raise ValueError(f"Unsupported priority: {priority}")
    return normalized


def _normalize_status(status: str) -> str:
    """Normalize and validate a ticket status."""

    normalized = status.strip().upper()
    if normalized not in TICKET_STATUSES:
        raise ValueError(f"Unsupported ticket status: {status}")
    return normalized


def _require_department(db: Session, department_id: int) -> Department:
    """Return a department or raise a clear service error."""

    department = db.get(Department, department_id)
    if department is None or not department.active:
        raise LookupError(f"Active department not found: {department_id}")
    return department


def _calculate_sla_due_at(department: Department, priority: str, start: datetime) -> datetime:
    """Calculate a department SLA deadline, halving it for high priority."""

    multiplier = 0.5 if priority == "high" else 1.0
    return start + timedelta(hours=department.sla_hours * multiplier)


def _add_audit_log(
    db: Session,
    *,
    actor: str,
    action: str,
    resource_id: str,
    metadata: dict[str, object],
) -> None:
    """Stage an audit record for the current transaction."""

    db.add(
        AuditLog(
            actor=actor,
            action=action,
            resource_type="ticket",
            resource_id=resource_id,
            metadata_json=metadata,
        )
    )


def _add_ticket_event(
    db: Session,
    *,
    ticket: Ticket,
    old_status: str | None,
    new_status: str,
    actor: str,
    note: str | None,
) -> None:
    """Stage a ticket event for the current transaction."""

    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            old_status=old_status,
            new_status=new_status,
            actor=actor,
            note=note,
        )
    )


def _commit_ticket(db: Session, ticket: Ticket) -> Ticket:
    """Commit a ticket transaction and leave the session usable after failures."""

    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(ticket)
    return ticket


def create_ticket(
    db: Session,
    *,
    original_text: str,
    language: str,
    user_id: int | None = None,
    department_id: int | None = None,
    translated_text: str | None = None,
    intent: str | None = None,
    priority: str = "medium",
    confidence: float | None = None,
    location_text: str | None = None,
    source_channel: str = "telegram",
    actor: str = "system",
) -> Ticket:
    """Create a ticket, its initial event and its creation audit record."""

    if not original_text.strip():
        raise ValueError("Complaint text cannot be empty")
    if not language.strip():
        raise ValueError("Language cannot be empty")
    if not source_channel.strip():
        raise ValueError("Source channel cannot be empty")
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0 and 1")

    normalized_priority = _normalize_priority(priority)
    now = datetime.now(UTC)
    department = _require_department(db, department_id) if department_id is not None else None
    status = "ASSIGNED" if department is not None else "NEW"
    ticket = Ticket(
        ticket_code=_temporary_ticket_code(),
        user_id=user_id,
        department_id=department.id if department else None,
        original_text=original_text.strip(),
        language=language.strip().lower(),
        translated_text=translated_text,
        intent=intent,
        priority=normalized_priority,
        confidence=confidence,
        status=status,
        location_text=location_text,
        source_channel=source_channel,
        sla_due_at=_calculate_sla_due_at(department, normalized_priority, now) if department else None,
    )
    db.add(ticket)
    try:
        db.flush()
    except SQLAlchemyError:
        db.rollback()
        raise

    ticket.ticket_code = f"GRV-{now.year}-{ticket.id:06d}"
    _add_ticket_event(
        db,
        ticket=ticket,
        old_status=None,
        new_status=status,
        actor=actor,
        note="Ticket created",
    )
    _add_audit_log(
        db,
        actor=actor,
        action="ticket_created",
        resource_id=ticket.ticket_code,
        metadata={"status": status, "department_id": department.id if department else None},
    )
    return _commit_ticket(db, ticket)


def get_ticket_by_code(db: Session, ticket_code: str) -> Ticket | None:
    """Return a ticket by its public code, or ``None`` when not found."""

    normalized_code = ticket_code.strip().upper()
    return db.scalar(select(Ticket).where(Ticket.ticket_code == normalized_code))


def assign_ticket(
    db: Session,
    *,
    ticket_code: str,
    department_id: int,
    actor: str = "system",
    note: str | None = None,
) -> Ticket:
    """Assign a ticket to an active department and set its SLA deadline."""

    ticket = get_ticket_by_code(db, ticket_code)
    if ticket is None:
        raise LookupError(f"Ticket not found: {ticket_code}")
    department = _require_department(db, department_id)
    old_status = ticket.status
    if ticket.status == "NEW":
        ticket.status = "ASSIGNED"
    ticket.department_id = department.id
    ticket.sla_due_at = _calculate_sla_due_at(department, ticket.priority, datetime.now(UTC))
    _add_ticket_event(
        db,
        ticket=ticket,
        old_status=old_status,
        new_status=ticket.status,
        actor=actor,
        note=note or f"Assigned to {department.name}",
    )
    _add_audit_log(
        db,
        actor=actor,
        action="ticket_assigned",
        resource_id=ticket.ticket_code,
        metadata={"department_id": department.id, "department_code": department.code},
    )
    return _commit_ticket(db, ticket)


def update_ticket_status(
    db: Session,
    *,
    ticket_code: str,
    new_status: str,
    actor: str = "system",
    note: str | None = None,
) -> Ticket:
    """Update a ticket status and record the event and audit entry."""

    ticket = get_ticket_by_code(db, ticket_code)
    if ticket is None:
        raise LookupError(f"Ticket not found: {ticket_code}")
    normalized_status = _normalize_status(new_status)
    old_status = ticket.status
    if old_status == normalized_status and not note:
        return ticket

    ticket.status = normalized_status
    if normalized_status == "ESCALATED" and old_status != "ESCALATED":
        ticket.escalation_level += 1
    _add_ticket_event(
        db,
        ticket=ticket,
        old_status=old_status,
        new_status=normalized_status,
        actor=actor,
        note=note,
    )
    _add_audit_log(
        db,
        actor=actor,
        action="ticket_status_updated",
        resource_id=ticket.ticket_code,
        metadata={"old_status": old_status, "new_status": normalized_status},
    )
    updated_ticket = _commit_ticket(db, ticket)
    try:
        from app.services.notifications import queue_status_notification

        queue_status_notification(db, updated_ticket)
    except Exception:
        logger.exception("Unable to queue status notification for %s", updated_ticket.ticket_code)
    return updated_ticket


def list_tickets_by_department(
    db: Session,
    *,
    department_id: int,
    status: str | None = None,
) -> list[Ticket]:
    """Return tickets for a department, optionally filtered by status."""

    return list_tickets(db, department_id=department_id, status=status)


def list_tickets(
    db: Session,
    *,
    department_id: int | None = None,
    status: str | None = None,
) -> list[Ticket]:
    """Return tickets with optional department and status filters."""

    statement = select(Ticket).order_by(Ticket.created_at.desc())
    if department_id is not None:
        statement = statement.where(Ticket.department_id == department_id)
    if status is not None:
        statement = statement.where(Ticket.status == _normalize_status(status))
    return list(db.scalars(statement).all())
