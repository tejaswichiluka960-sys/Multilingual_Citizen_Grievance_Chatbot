"""SLA escalation logic for overdue grievance tickets."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Ticket
from app.services.tickets import update_ticket_status

ACTIVE_STATUSES = frozenset({"NEW", "ASSIGNED", "IN_PROGRESS", "REOPENED"})


@dataclass(frozen=True, slots=True)
class EscalationSummary:
    """Counts produced by one escalation pass."""

    checked: int
    escalated: int


def find_overdue_tickets(db: Session, now: datetime | None = None) -> list[Ticket]:
    """Return active tickets whose SLA deadline has passed."""

    current_time = now or datetime.now(UTC)
    statement = (
        select(Ticket)
        .where(
            Ticket.sla_due_at.is_not(None),
            Ticket.sla_due_at <= current_time,
            Ticket.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Ticket.sla_due_at)
    )
    return list(db.scalars(statement).all())


def escalate_overdue_tickets(
    db: Session,
    *,
    now: datetime | None = None,
    actor: str = "escalation-worker",
) -> EscalationSummary:
    """Escalate each overdue active ticket exactly once per status transition."""

    overdue = find_overdue_tickets(db, now)
    escalated = 0
    for ticket in overdue:
        update_ticket_status(
            db,
            ticket_code=ticket.ticket_code,
            new_status="ESCALATED",
            actor=actor,
            note="SLA deadline exceeded; automatically escalated.",
        )
        escalated += 1
    return EscalationSummary(checked=len(overdue), escalated=escalated)
