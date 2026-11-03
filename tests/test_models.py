"""Schema tests using an isolated in-memory SQLite database."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Department, Ticket, TicketEvent, User


def test_all_expected_tables_are_registered() -> None:
    expected = {
        "users",
        "departments",
        "tickets",
        "ticket_events",
        "notifications",
        "admin_users",
        "audit_logs",
    }

    assert expected.issubset(Base.metadata.tables.keys())


def test_ticket_relationships_work_with_sqlite() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        user = User(telegram_id="123", preferred_lang="te")
        department = Department(code="WATER", name="Water Supply and Sewerage")
        ticket = Ticket(
            ticket_code="GRV-2026-000001",
            original_text="There is a water leak near my street.",
            language="en",
            priority="high",
            user=user,
            department=department,
        )
        ticket.events.append(TicketEvent(new_status="NEW", actor="system"))
        session.add(ticket)
        session.commit()

        saved_ticket = session.scalar(select(Ticket).where(Ticket.ticket_code == "GRV-2026-000001"))

        assert saved_ticket is not None
        assert saved_ticket.user is not None
        assert saved_ticket.user.preferred_lang == "te"
        assert saved_ticket.department is not None
        assert saved_ticket.department.code == "WATER"
        assert len(saved_ticket.events) == 1
