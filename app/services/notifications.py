"""Localized Telegram notification queue and delivery service."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Notification, Ticket
from app.services.localization import localized_message

logger = logging.getLogger(__name__)

NotificationSender = Callable[[str, str], None]


def _status_label(status: str, language: str) -> str:
    """Return a localized status label from the message catalogs."""

    return localized_message(f"status_{status.lower()}", language)


def queue_status_notification(db: Session, ticket: Ticket) -> Notification | None:
    """Queue one localized notification for a Telegram-linked ticket."""

    if ticket.user is None or not ticket.user.telegram_id:
        return None
    language = ticket.user.preferred_lang or ticket.language or "en"
    message = localized_message(
        "status_update",
        language,
        ticket_code=ticket.ticket_code,
        status=_status_label(ticket.status, language),
    )
    existing = db.scalar(
        select(Notification).where(
            Notification.ticket_id == ticket.id,
            Notification.message == message,
            Notification.delivery_status == "PENDING",
        )
    )
    if existing is not None:
        return existing

    notification = Notification(
        ticket_id=ticket.id,
        channel="telegram",
        recipient=ticket.user.telegram_id,
        language=language,
        message=message,
        delivery_status="PENDING",
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def send_telegram_message(recipient: str, message: str, token: str | None = None) -> None:
    """Send one Telegram message through the synchronous Bot API."""

    bot_token = token or get_settings().telegram_bot_token
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required for notification delivery")
    response = httpx.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data={"chat_id": recipient, "text": message},
        timeout=15.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError("Telegram rejected the notification")


def deliver_pending_notifications(
    db: Session,
    *,
    sender: NotificationSender | None = None,
    limit: int = 50,
) -> int:
    """Deliver pending notifications and mark each result for retry visibility."""

    if limit <= 0:
        raise ValueError("Notification limit must be positive")
    notifications = list(
        db.scalars(
            select(Notification)
            .where(Notification.delivery_status == "PENDING")
            .order_by(Notification.created_at)
            .limit(limit)
        ).all()
    )
    delivered = 0
    for notification in notifications:
        try:
            if sender is None:
                send_telegram_message(notification.recipient, notification.message)
            else:
                sender(notification.recipient, notification.message)
        except Exception:
            logger.exception("Notification delivery failed: %s", notification.id)
            notification.delivery_status = "FAILED"
            continue
        notification.delivery_status = "SENT"
        notification.sent_at = datetime.now(UTC)
        delivered += 1
    db.commit()
    return delivered
