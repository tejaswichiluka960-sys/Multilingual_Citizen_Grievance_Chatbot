"""Tests for the browser chat endpoint and page."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.chat import chat_route
from app.db import Base
from app.schemas import ChatRequest
from app.services import classifier
from app.services.auth import create_session, register_user
from app.services.departments import seed_departments
from app.services.tickets import update_ticket_status
from app.web.routes import chat_page


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
        assert response.status == "ASSIGNED"
        assert "ticket" in response.reply.lower()
    finally:
        session.close()


def test_chat_clarification_button_creates_ticket(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
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
        assert 'fetch("/chat"' in page.body.decode()
    finally:
        session.close()
