"""Command-line database initialization entry point."""

from app.db import SessionLocal, initialize_database
from app.services.departments import seed_departments


def main() -> None:
    """Create the database tables for the configured database URL."""

    initialize_database()
    with SessionLocal() as db:
        summary = seed_departments(db)
    print(
        "Database initialized: "
        f"{summary.created} departments created, "
        f"{summary.updated} updated, "
        f"{summary.unchanged} unchanged."
    )


if __name__ == "__main__":
    main()
