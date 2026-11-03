"""Structured logging setup for the application."""

import logging


def configure_logging(level: str) -> None:
    """Configure application-wide logging using an environment-driven level."""

    normalized_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=normalized_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
