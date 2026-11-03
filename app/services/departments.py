"""Department reference-data services."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department
from app.seed_data import DEPARTMENT_SEEDS


@dataclass(frozen=True, slots=True)
class SeedSummary:
    """Counts produced by an idempotent department seed operation."""

    created: int
    updated: int
    unchanged: int


def seed_departments(db: Session) -> SeedSummary:
    """Insert or refresh the standard department records without duplicates."""

    created = 0
    updated = 0
    unchanged = 0

    for seed in DEPARTMENT_SEEDS:
        department = db.scalar(select(Department).where(Department.code == seed.code))
        if department is None:
            db.add(
                Department(
                    code=seed.code,
                    name=seed.name,
                    sla_hours=seed.sla_hours,
                    active=seed.active,
                )
            )
            created += 1
            continue

        changed = (
            department.name != seed.name
            or department.sla_hours != seed.sla_hours
            or department.active != seed.active
        )
        department.name = seed.name
        department.sla_hours = seed.sla_hours
        department.active = seed.active
        if changed:
            updated += 1
        else:
            unchanged += 1

    db.commit()
    return SeedSummary(created=created, updated=updated, unchanged=unchanged)
