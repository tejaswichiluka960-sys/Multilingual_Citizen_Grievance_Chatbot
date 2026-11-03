"""Tests for the FastAPI ticket route functions."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.tickets import (
    create_ticket_route,
    get_ticket_route,
    list_admin_tickets_route,
    update_ticket_status_route,
)
from app.db import Base
from app.models import Department
from app.schemas import TicketCreateRequest, TicketStatusUpdateRequest
from app.services.departments import seed_departments


def make_session() -> Session:
    """Create an isolated session for route tests."""

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
    """Return a seeded department ID."""

    department = session.scalar(select(Department).where(Department.code == code))
    assert department is not None
    return department.id


def test_ticket_routes_create_get_update_and_filter() -> None:
    session = make_session()
    try:
        created = create_ticket_route(
            TicketCreateRequest(
                original_text="There is a pothole near the market.",
                language="en",
                department_id=department_id(session, "ROADS"),
                priority="medium",
                source_channel="web",
            ),
            session,
        )
        fetched = get_ticket_route(created.ticket_code, session)
        updated = update_ticket_status_route(
            created.ticket_code,
            TicketStatusUpdateRequest(
                new_status="IN_PROGRESS",
                actor="officer-1",
                note="Assigned for inspection.",
            ),
            session,
        )
        filtered = list_admin_tickets_route(department="ROADS", status_value="IN_PROGRESS", db=session)

        assert created.ticket_code.startswith("GRV-")
        assert created.department_code == "ROADS"
        assert fetched.ticket_code == created.ticket_code
        assert updated.status == "IN_PROGRESS"
        assert len(updated.events) == 2
        assert len(filtered) == 1
        assert filtered[0].ticket_code == created.ticket_code
    finally:
        session.close()


def test_unknown_department_filter_returns_empty_queue() -> None:
    session = make_session()
    try:
        assert list_admin_tickets_route(department="UNKNOWN", status_value=None, db=session) == []
    finally:
        session.close()
