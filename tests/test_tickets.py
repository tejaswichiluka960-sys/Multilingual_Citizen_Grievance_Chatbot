"""Unit tests for the ticket service."""

import re

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AuditLog, Department, Ticket, User
from app.services.departments import seed_departments
from app.services.tickets import (
    assign_ticket,
    create_ticket,
    get_ticket_by_code,
    list_tickets,
    update_ticket_status,
)


def make_session() -> Session:
    """Create a session connected to an isolated in-memory database."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    seed_departments(session)
    return session


def get_department_id(session: Session, code: str) -> int:
    """Return a seeded department ID for tests."""

    department = session.scalar(select(Department).where(Department.code == code))
    assert department is not None
    return department.id


def test_create_ticket_generates_code_sla_event_and_audit() -> None:
    session = make_session()
    try:
        user = User(telegram_id="citizen-1", preferred_lang="te")
        session.add(user)
        session.commit()

        ticket = create_ticket(
            session,
            original_text="There is an exposed electric wire near the school.",
            language="en",
            user_id=user.id,
            department_id=get_department_id(session, "POWER"),
            priority="high",
            confidence=0.91,
            location_text="Main Road",
        )

        assert re.fullmatch(r"GRV-\d{4}-\d{6}", ticket.ticket_code)
        assert ticket.status == "ASSIGNED"
        assert ticket.sla_due_at is not None
        assert len(ticket.events) == 1
        assert ticket.events[0].new_status == "ASSIGNED"
        audit = session.scalar(select(AuditLog).where(AuditLog.resource_id == ticket.ticket_code))
        assert audit is not None
        assert audit.action == "ticket_created"
    finally:
        session.close()


def test_assign_and_update_status_record_history() -> None:
    session = make_session()
    try:
        ticket = create_ticket(
            session,
            original_text="Garbage has not been collected for several days.",
            language="en",
            source_channel="web",
        )
        assigned = assign_ticket(
            session,
            ticket_code=ticket.ticket_code,
            department_id=get_department_id(session, "SANITATION"),
            actor="officer-1",
        )
        resolved = update_ticket_status(
            session,
            ticket_code=assigned.ticket_code,
            new_status="RESOLVED",
            actor="officer-1",
            note="Collection completed.",
        )

        session.refresh(resolved)
        assert resolved.status == "RESOLVED"
        assert resolved.department is not None
        assert resolved.department.code == "SANITATION"
        assert [event.new_status for event in resolved.events] == ["NEW", "ASSIGNED", "RESOLVED"]
        assert len(session.scalars(select(AuditLog).where(AuditLog.resource_id == resolved.ticket_code)).all()) == 3
        assert get_ticket_by_code(session, resolved.ticket_code) is not None
    finally:
        session.close()


def test_invalid_ticket_inputs_raise_clear_errors() -> None:
    session = make_session()
    try:
        with pytest.raises(ValueError, match="Complaint text"):
            create_ticket(session, original_text=" ", language="en")
        with pytest.raises(ValueError, match="Unsupported priority"):
            create_ticket(session, original_text="No water", language="en", priority="urgent")
        with pytest.raises(ValueError, match="Confidence"):
            create_ticket(session, original_text="No water", language="en", confidence=1.1)
        with pytest.raises(ValueError, match="Source channel"):
            create_ticket(session, original_text="No water", language="en", source_channel=" ")
        with pytest.raises(LookupError, match="Active department"):
            create_ticket(session, original_text="No water", language="en", department_id=9999)
        with pytest.raises(LookupError, match="Ticket not found"):
            update_ticket_status(session, ticket_code="GRV-2026-999999", new_status="RESOLVED")
    finally:
        session.close()


def test_ticket_codes_are_unique_and_inputs_are_normalized() -> None:
    session = make_session()
    try:
        first = create_ticket(
            session,
            original_text="  No water in our area.  ",
            language=" HI ",
            priority=" HIGH ",
        )
        second = create_ticket(session, original_text="Power is out.", language="EN")

        assert first.ticket_code != second.ticket_code
        assert first.original_text == "No water in our area."
        assert first.language == "hi"
        assert first.priority == "high"
        assert get_ticket_by_code(session, first.ticket_code.lower()) is not None
        assert get_ticket_by_code(session, " ") is None
    finally:
        session.close()


def test_repeated_status_is_a_safe_noop_and_escalation_counts_once() -> None:
    session = make_session()
    try:
        ticket = create_ticket(session, original_text="There is a safety hazard.", language="en")
        escalated = update_ticket_status(session, ticket_code=ticket.ticket_code, new_status="ESCALATED")
        repeated = update_ticket_status(session, ticket_code=ticket.ticket_code, new_status="ESCALATED")
        session.refresh(repeated)

        assert escalated.escalation_level == 1
        assert repeated.escalation_level == 1
        assert len(repeated.events) == 2
        audits = session.scalars(select(AuditLog).where(AuditLog.resource_id == ticket.ticket_code)).all()
        assert len(audits) == 2
    finally:
        session.close()


def test_department_and_status_filters_return_only_matching_tickets() -> None:
    session = make_session()
    try:
        water_id = get_department_id(session, "WATER")
        power_id = get_department_id(session, "POWER")
        water_ticket = create_ticket(
            session,
            original_text="The water line is leaking.",
            language="en",
            department_id=water_id,
        )
        create_ticket(
            session,
            original_text="The power line is damaged.",
            language="en",
            department_id=power_id,
        )
        update_ticket_status(session, ticket_code=water_ticket.ticket_code, new_status="IN_PROGRESS")

        water_tickets = list_tickets(session, department_id=water_id)
        in_progress = list_tickets(session, status="in_progress")

        assert len(water_tickets) == 1
        assert water_tickets[0].ticket_code == water_ticket.ticket_code
        assert len(in_progress) == 1
        assert in_progress[0].ticket_code == water_ticket.ticket_code
    finally:
        session.close()


def test_duplicate_public_code_is_rejected_and_session_recovers() -> None:
    session = make_session()
    try:
        first = create_ticket(session, original_text="First complaint.", language="en")
        duplicate = Ticket(
            ticket_code=first.ticket_code,
            original_text="Duplicate complaint.",
            language="en",
        )
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        second = create_ticket(session, original_text="Second complaint.", language="en")
        assert second.ticket_code != first.ticket_code
    finally:
        session.close()
