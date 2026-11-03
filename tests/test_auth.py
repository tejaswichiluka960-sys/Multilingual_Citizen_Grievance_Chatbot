"""Tests for citizen registration, login and language preference sessions."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.services.auth import (
    authenticate_user,
    create_session,
    get_user_from_session,
    register_user,
)


def make_session() -> Session:
    """Create an isolated authentication database."""

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_register_login_and_language_session() -> None:
    """A citizen can register, authenticate and recover the selected language."""

    session = make_session()
    try:
        user = register_user(
            session,
            username="citizen-one",
            password="StrongPassword123!",
            name="Citizen One",
            language="hi",
        )
        assert user.preferred_lang == "hi"
        assert authenticate_user(session, username="citizen-one", password="StrongPassword123!") is not None
        assert authenticate_user(session, username="citizen-one", password="wrong-password") is None

        token = create_session(session, user.id)
        restored = get_user_from_session(session, token)
        assert restored is not None
        assert restored.id == user.id
        assert restored.preferred_lang == "hi"
    finally:
        session.close()


def test_duplicate_username_is_rejected() -> None:
    """Usernames cannot be registered twice."""

    session = make_session()
    try:
        register_user(session, username="citizen-one", password="StrongPassword123!", name="One", language="en")
        try:
            register_user(session, username="CITIZEN-ONE", password="StrongPassword123!", name="Two", language="te")
        except ValueError as exc:
            assert "already registered" in str(exc)
        else:
            raise AssertionError("Duplicate username was accepted")
    finally:
        session.close()
