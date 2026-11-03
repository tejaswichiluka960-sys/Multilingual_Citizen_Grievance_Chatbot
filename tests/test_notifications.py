"""Tests for localized notification delivery and SLA escalation."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Department, Notification, User
from app.services.departments import seed_departments
from app.services.escalation import escalate_overdue_tickets
from app.services.notifications import deliver_pending_notifications
from app.services.tickets import create_ticket, update_ticket_status


def make_session() -> Session:
    """Create an isolated database session with seeded departments."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    seed_departments(session)
    return session


def department_id(session: Session, code: str) -> int:
    """Return one seeded department ID."""

    department = session.scalar(select(Department).where(Department.code == code))
    assert department is not None
    return department.id


def test_status_update_queues_localized_notification_and_delivers_it() -> None:
    session = make_session()
    try:
        user = User(telegram_id="telegram-1", preferred_lang="hi", name="Citizen")
        session.add(user)
        session.commit()
        ticket = create_ticket(
            session,
            original_text="पानी नहीं आ रहा है",
            language="hi",
            user_id=user.id,
            department_id=department_id(session, "WATER"),
        )

        update_ticket_status(session, ticket_code=ticket.ticket_code, new_status="RESOLVED")
        notification = session.scalar(select(Notification))
        assert notification is not None
        assert notification.delivery_status == "PENDING"
        assert "स्थिति" in notification.message

        sent: list[tuple[str, str]] = []

        def sender(recipient: str, message: str) -> None:
            sent.append((recipient, message))

        delivered = deliver_pending_notifications(session, sender=sender)

        assert delivered == 1
        session.refresh(notification)
        assert notification.delivery_status == "SENT"
        assert sent[0][0] == "telegram-1"
    finally:
        session.close()


def test_escalation_worker_updates_overdue_ticket_once() -> None:
    session = make_session()
    try:
        user = User(telegram_id="telegram-2", preferred_lang="en", name="Citizen")
        session.add(user)
        session.commit()
        ticket = create_ticket(
            session,
            original_text="Water supply stopped.",
            language="en",
            user_id=user.id,
            department_id=department_id(session, "WATER"),
        )
        ticket.sla_due_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

        summary = escalate_overdue_tickets(session)

        assert summary.checked == 1
        assert summary.escalated == 1
        session.refresh(ticket)
        assert ticket.status == "ESCALATED"
        assert ticket.escalation_level == 1
        assert len(session.scalars(select(Notification)).all()) == 1

        second_summary = escalate_overdue_tickets(session)
        assert second_summary.checked == 0
        assert second_summary.escalated == 0
    finally:
        session.close()
