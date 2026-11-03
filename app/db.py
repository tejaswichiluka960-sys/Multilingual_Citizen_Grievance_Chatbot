"""Database engine and session setup."""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
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

    Base.metadata.create_all(bind=engine)


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
