"""Tests for the shared complaint-intake orchestration."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Department
from app.services import classifier
from app.services.departments import seed_departments
from app.services.intake import (
    create_prepared_ticket,
    prepare_complaint,
    upsert_telegram_user,
)


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


def test_prepare_complaint_detects_and_routes_water(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)

    prepared = prepare_complaint("There is no water supply near my street", "en")

    assert prepared.language == "en"
    assert prepared.department_code == "WATER"
    assert prepared.intent == "water_supply"
    assert prepared.needs_clarification is False


def test_prepare_complaint_requests_clarification_for_ambiguous_text(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    monkeypatch.setattr(classifier, "get_ai_router", lambda: None)

    prepared = prepare_complaint("Please help with this problem", "hi")

    assert prepared.language == "en"
    assert prepared.department_code == "OTHER"
    assert prepared.needs_clarification is True


def test_user_upsert_and_prepared_ticket_preserve_original_and_translation(monkeypatch) -> None:
    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    session = make_session()
    try:
        user = upsert_telegram_user(
            session,
            telegram_id="telegram-123",
            name="Citizen",
            language="te",
        )
        prepared = prepare_complaint("మా వీధిలో నీటి సరఫరా లేదు", "te")
        ticket = create_prepared_ticket(session, prepared=prepared, user_id=user.id)
        department = session.scalar(select(Department).where(Department.code == "WATER"))

        assert ticket.ticket_code.startswith("GRV-")
        assert ticket.original_text == "మా వీధిలో నీటి సరఫరా లేదు"
        assert ticket.language == "te"
        assert ticket.department_id == department.id
        assert ticket.translated_text
        assert ticket.user_id == user.id
    finally:
        session.close()
