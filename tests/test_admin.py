"""Tests for the officer dashboard rendering and status update route."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.admin.routes import render_admin_dashboard, update_admin_ticket_status
from app.db import Base
from app.models import Department
from app.services.departments import seed_departments
from app.services.tickets import create_ticket


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


def test_admin_dashboard_renders_ticket_and_filters() -> None:
    session = make_session()
    try:
        ticket = create_ticket(
            session,
            original_text="There is a pothole near the market.",
            language="en",
            department_id=department_id(session, "ROADS"),
            source_channel="web",
        )
        departments = list(session.scalars(select(Department)).all())

        response = render_admin_dashboard(
            [ticket],
            departments,
            selected_department="ROADS",
            selected_status="ASSIGNED",
        )

        assert response.status_code == 200
        assert ticket.ticket_code in response.body.decode()
        assert "Officer Dashboard" in response.body.decode()
        assert 'value="ROADS" selected' in response.body.decode()
    finally:
        session.close()


def test_admin_status_update_redirects_and_changes_ticket() -> None:
    session = make_session()
    try:
        ticket = create_ticket(session, original_text="No water supply.", language="en")

        response = update_admin_ticket_status(
            ticket.ticket_code,
            new_status="IN_PROGRESS",
            note="Officer assigned for inspection.",
            admin_user="officer-1",
            db=session,
        )

        session.refresh(ticket)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/admin?")
        assert ticket.status == "IN_PROGRESS"
        assert ticket.events[-1].actor == "officer-1"
        assert ticket.events[-1].note == "Officer assigned for inspection."
    finally:
        session.close()
