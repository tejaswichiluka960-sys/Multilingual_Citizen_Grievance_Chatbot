"""Database engine and session setup."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def initialize_database() -> None:
    """Create all registered tables in the configured database."""

    from app import models  # noqa: F401  # Register model metadata before create_all.

    _ensure_user_auth_columns()
    Base.metadata.create_all(bind=engine)
    _ensure_user_auth_columns()


def _ensure_user_auth_columns() -> None:
    """Add authentication columns to databases created before citizen login."""

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []
    if "username" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN username VARCHAR(100)")
    if "password_hash" not in columns:
        statements.append("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))


def check_database_connection() -> bool:
    """Return whether the configured database accepts a simple query."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        return False
    return True


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for request handlers."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
