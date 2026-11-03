"""Tests for department reference data and idempotent seeding."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Department
from app.services.departments import seed_departments


def make_engine():
    """Create an isolated in-memory database for the test."""

    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_seed_creates_all_departments() -> None:
    engine = make_engine()
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        summary = seed_departments(db)
        departments = db.scalars(select(Department).order_by(Department.code)).all()

    assert summary.created == 10
    assert summary.updated == 0
    assert summary.unchanged == 0
    assert len(departments) == 10
    assert departments[0].code == "EDUCATION"
    assert any(department.code == "WATER" and department.sla_hours == 48 for department in departments)
    assert any(department.code == "POLICE" and department.sla_hours == 4 for department in departments)


def test_seed_is_idempotent_and_refreshes_changed_values() -> None:
    engine = make_engine()
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        first = seed_departments(db)
        second = seed_departments(db)
        water = db.scalar(select(Department).where(Department.code == "WATER"))
        assert water is not None
        water.sla_hours = 999
        db.commit()
        third = seed_departments(db)
        refreshed_water = db.scalar(select(Department).where(Department.code == "WATER"))

    assert first.created == 10
    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == 10
    assert third.updated == 1
    assert refreshed_water is not None
    assert refreshed_water.sla_hours == 48
