"""Tests for the browser chat endpoint and page."""

from datetime import date, time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.chat import chat_route
from app.db import Base
from app.models import Ticket
from app.schemas import ChatRequest
from app.services import classifier
from app.services.auth import create_session, register_user
from app.services.departments import seed_departments
from app.services.tickets import update_ticket_status
from app.web.routes import chat_page, my_tickets_page, profile_page


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


def test_chat_creates_web_ticket(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    session = make_session()
    try:
        response = chat_route(
            ChatRequest(message="There is no water supply near my street", language="en"),
            session,
        )

        assert response.ticket_code is not None
        assert response.department_code == "WATER"
        assert response.intent == "water_supply"
        assert response.confidence is not None
        assert response.status == "ASSIGNED"
        assert "ticket" in response.reply.lower()
    finally:
        session.close()


def test_chat_stores_address_and_incident_date_time(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    session = make_session()
    try:
        response = chat_route(
            ChatRequest(
                message="A streetlight is not working",
                language="en",
                address="12 Main Road, Ward 4",
                incident_date=date(2026, 11, 4),
                incident_time=time(19, 30),
            ),
            session,
        )

        ticket = session.scalar(select(Ticket).where(Ticket.ticket_code == response.ticket_code))
        assert ticket is not None
        assert ticket.location_text == "12 Main Road, Ward 4"
        assert ticket.incident_date == date(2026, 11, 4)
        assert ticket.incident_time == time(19, 30)
        assert response.address == "12 Main Road, Ward 4"
        assert response.incident_date == date(2026, 11, 4)
        assert response.incident_time == time(19, 30)
    finally:
        session.close()


def test_chat_clarification_button_creates_ticket(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    monkeypatch.setattr(classifier, "get_ai_router", lambda: None)
    session = make_session()
    try:
        clarification = chat_route(
            ChatRequest(session_id="web-clarification", message="Please help with this problem"),
            session,
        )
        assert clarification.ticket_code is None
        assert len(clarification.choices) == 10

        created = chat_route(
            ChatRequest(
                session_id=clarification.session_id,
                language="en",
                department_code="OTHER",
            ),
            session,
        )

        assert created.ticket_code is not None
        assert created.department_code == "OTHER"
    finally:
        session.close()


def test_chat_status_lookup_and_html_page(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    session = make_session()
    try:
        created = chat_route(ChatRequest(message="The road has a large pothole"), session)
        assert created.ticket_code is not None
        update_ticket_status(session, ticket_code=created.ticket_code, new_status="IN_PROGRESS")
        status_response = chat_route(
            ChatRequest(session_id="status-session", message=f"/status {created.ticket_code}"),
            session,
        )
        assert status_response.status == "IN_PROGRESS"
        assert "In progress" in status_response.reply
        user = register_user(
            session,
            username="chat-user",
            password="StrongPassword123!",
            name="Chat User",
            language="en",
        )
        token = create_session(session, user.id)
        owned = chat_route(
            ChatRequest(message="There is no water supply", address="Ward 4 Main Road"),
            session,
            user.id,
        )
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/chat",
                "headers": [(b"cookie", f"citizen_session={token}".encode())],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
                "scheme": "http",
            }
        )
        page = chat_page(request, session)
        assert page.status_code == 200
        page_body = page.body.decode()
        assert 'fetch("/chat"' in page_body
        assert '"sending": "Sending..."' in page_body
        assert '"failed_to_send": "Failed to send"' in page_body
        assert 'id="home-link"' in page_body
        assert 'id="tickets-link"' in page_body
        tickets_page = my_tickets_page(request, db=session)
        assert tickets_page.status_code == 200
        tickets_body = tickets_page.body.decode()
        assert owned.ticket_code in tickets_body
        assert "Ward 4 Main Road" in tickets_body
        assert "Status tracking" in tickets_body
        assert "Ticket created" in tickets_body
        assert "Routed to department" in tickets_body
        assert "Department: Water" in tickets_body
        searched_page = my_tickets_page(request, ticket_code=owned.ticket_code, db=session)
        searched_body = searched_page.body.decode()
        assert owned.ticket_code in searched_body
        assert "GRV-2026-" not in searched_body.replace(owned.ticket_code, "")
        profile = profile_page(request, session)
        assert profile.status_code == 200
        assert "Chat User" in profile.body.decode()
    finally:
        session.close()
