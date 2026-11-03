"""APScheduler integration for SLA escalation and Telegram delivery."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.db import SessionLocal
from app.services.escalation import escalate_overdue_tickets
from app.services.notifications import deliver_pending_notifications

logger = logging.getLogger(__name__)


def run_escalation_job() -> None:
    """Run one database-backed escalation pass."""

    with SessionLocal() as db:
        summary = escalate_overdue_tickets(db)
    if summary.escalated:
        logger.info("Escalation worker updated %s overdue ticket(s)", summary.escalated)


def run_notification_job() -> None:
    """Run one asynchronous Telegram notification pass."""

    with SessionLocal() as db:
        delivered = deliver_pending_notifications(db)
    if delivered:
        logger.info("Notification worker delivered %s message(s)", delivered)


def start_background_scheduler() -> BackgroundScheduler:
    """Start recurring escalation and notification jobs."""

    interval = get_settings().escalation_interval_minutes
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(run_escalation_job, "interval", minutes=interval, id="sla-escalation", replace_existing=True)
    scheduler.add_job(run_notification_job, "interval", minutes=interval, id="telegram-notifications", replace_existing=True)
    scheduler.start()
    logger.info("Background workers started with a %s-minute interval", interval)
    return scheduler
