"""Stable reference data used to initialize the grievance database."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DepartmentSeed:
    """Reference values for a department record."""

    code: str
    name: str
    sla_hours: float
    active: bool = True


DEPARTMENT_SEEDS: tuple[DepartmentSeed, ...] = (
    DepartmentSeed("WATER", "Water Supply and Sewerage", 48),
    DepartmentSeed("POWER", "Electricity", 24),
    DepartmentSeed("ROADS", "Roads and Infrastructure", 72),
    DepartmentSeed("SANITATION", "Sanitation and Solid Waste", 48),
    DepartmentSeed("POLICE", "Police and Public Safety", 4),
    DepartmentSeed("HEALTH", "Health", 24),
    DepartmentSeed("EDUCATION", "Education", 72),
    DepartmentSeed("TRANSPORT", "Transport", 48),
    DepartmentSeed("REVENUE", "Revenue, Land and Certificates", 120),
    DepartmentSeed("OTHER", "Other or Human Review", 72),
)
