"""Citizen registration, password hashing and browser sessions."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserSession

PASSWORD_ITERATIONS = 310_000
SESSION_DAYS = 7


def hash_password(password: str) -> str:
    """Hash a password with a per-password salt using PBKDF2-SHA256."""

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Verify a password hash without exposing timing information."""

    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(salt_hex),
            int(iterations),
        ).hex()
    except (TypeError, ValueError):
        return False
    return secrets.compare_digest(expected, digest_hex)


def register_user(db: Session, *, username: str, password: str, name: str, language: str) -> User:
    """Create a citizen account after validating uniqueness and credentials."""

    normalized_username = username.strip().lower()
    if len(normalized_username) < 3 or len(normalized_username) > 100:
        raise ValueError("Username must contain 3 to 100 characters")
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must contain 8 to 128 characters")
    if db.scalar(select(User).where(User.username == normalized_username)) is not None:
        raise ValueError("Username is already registered")
    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        name=name.strip()[:150],
        preferred_lang=language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    """Return a citizen user when the username and password are valid."""

    user = db.scalar(select(User).where(User.username == username.strip().lower()))
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, user_id: int) -> str:
    """Create a random browser token and persist only its hash."""

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db.add(
        UserSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
        )
    )
    db.execute(delete(UserSession).where(UserSession.expires_at < datetime.now(UTC)))
    db.commit()
    return raw_token


def get_user_from_session(db: Session, raw_token: str | None) -> User | None:
    """Resolve a non-expired browser cookie to a citizen user."""

    if not raw_token:
        return None
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    return session.user if session is not None else None


def get_optional_user_id(
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> int | None:
    """Return the logged-in citizen ID for browser API requests, if present."""

    user = get_user_from_session(db, request.cookies.get("citizen_session"))
    return user.id if user is not None else None
