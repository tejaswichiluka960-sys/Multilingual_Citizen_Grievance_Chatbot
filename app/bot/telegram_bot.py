"""Telegram bot foundation and localized language-selection handlers."""

import logging
import re
from collections.abc import Mapping

from sqlalchemy.exc import SQLAlchemyError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import InvalidToken, NetworkError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import get_settings
from app.db import SessionLocal, initialize_database
from app.logging_config import configure_logging
from app.models import Ticket
from app.services.departments import seed_departments
from app.services.intake import (
    PreparedComplaint,
    create_prepared_ticket,
    prepare_complaint,
    upsert_telegram_user,
)
from app.services.localization import localized_message
from app.services.tickets import get_ticket_by_code
from app.workers.scheduler import start_background_scheduler

logger = logging.getLogger(__name__)

LANGUAGE_CALLBACK_PREFIX = "language:"
LANGUAGE_CALLBACKS = {
    f"{LANGUAGE_CALLBACK_PREFIX}en": "en",
    f"{LANGUAGE_CALLBACK_PREFIX}hi": "hi",
    f"{LANGUAGE_CALLBACK_PREFIX}te": "te",
}
DEPARTMENT_CALLBACK_PREFIX = "department:"
DEPARTMENT_CODES = (
    "WATER",
    "POWER",
    "ROADS",
    "SANITATION",
    "POLICE",
    "HEALTH",
    "EDUCATION",
    "TRANSPORT",
    "REVENUE",
    "OTHER",
)
TICKET_CODE_PATTERN = re.compile(r"^GRV-\d{4}-\d{6}$", re.IGNORECASE)


def language_keyboard() -> InlineKeyboardMarkup:
    """Build the language picker shown by the start command."""

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    localized_message("language_name_en", "en"),
                    callback_data=f"{LANGUAGE_CALLBACK_PREFIX}en",
                ),
                InlineKeyboardButton(
                    localized_message("language_name_hi", "hi"),
                    callback_data=f"{LANGUAGE_CALLBACK_PREFIX}hi",
                ),
                InlineKeyboardButton(
                    localized_message("language_name_te", "te"),
                    callback_data=f"{LANGUAGE_CALLBACK_PREFIX}te",
                ),
            ]
        ]
    )


def department_keyboard(language: str) -> InlineKeyboardMarkup:
    """Build department buttons used when classification needs clarification."""

    buttons = [
        InlineKeyboardButton(
            localized_message(f"department_{code.lower()}", language),
            callback_data=f"{DEPARTMENT_CALLBACK_PREFIX}{code}",
        )
        for code in DEPARTMENT_CODES
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


def get_user_language(user_data: Mapping[str, object] | None) -> str:
    """Return a validated language stored in Telegram user state."""

    language = str((user_data or {}).get("language", "en")).strip().lower()
    return language if language in {"en", "hi", "te"} else "en"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome a citizen and ask for the preferred response language."""

    if update.message is None:
        return
    language = get_user_language(context.user_data)
    await update.message.reply_text(
        f"{localized_message('welcome', language)}\n"
        f"{localized_message('choose_language', language)}",
        reply_markup=language_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain the commands available at the current bot stage."""

    if update.message is None:
        return
    language = get_user_language(context.user_data)
    await update.message.reply_text(localized_message("help", language))


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel the current conversation without deleting stored tickets."""

    if update.message is None:
        return
    language = get_user_language(context.user_data)
    context.user_data.clear()
    context.user_data["language"] = language
    await update.message.reply_text(localized_message("cancelled", language))


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Store a selected language and prompt the citizen for a complaint."""

    query = update.callback_query
    if query is None:
        return
    await query.answer()
    language = LANGUAGE_CALLBACKS.get(query.data or "")
    if language is None:
        await query.edit_message_text(localized_message("error_generic", "en"))
        return

    context.user_data["language"] = language
    language_name = localized_message(f"language_name_{language}", language)
    await query.edit_message_text(localized_message("language_confirmed", language, language=language_name))
    if query.message is not None:
        await query.message.reply_text(localized_message("complaint_prompt", language))


def _telegram_user_details(update: Update) -> tuple[str, str | None] | None:
    """Return a stable Telegram user ID and optional display name."""

    user = update.effective_user
    if user is None:
        return None
    return str(user.id), user.full_name


def _department_label(department_code: str, language: str) -> str:
    """Return a localized display label for a department code."""

    return localized_message(f"department_{department_code.lower()}", language)


def _status_label(status: str, language: str) -> str:
    """Return a localized display label for a ticket status."""

    return localized_message(f"status_{status.lower()}", language)


def _ticket_confirmation(ticket: Ticket, language: str) -> str:
    """Format the localized ticket-created response."""

    department_code = ticket.department.code if ticket.department else "OTHER"
    return localized_message(
        "ticket_created_with_id",
        language,
        ticket_code=ticket.ticket_code,
        department=_department_label(department_code, language),
    )


async def _send_status(message, ticket_code: str, language: str) -> None:
    """Look up one ticket and send its localized status."""

    normalized_code = ticket_code.strip().upper()
    if not TICKET_CODE_PATTERN.fullmatch(normalized_code):
        await message.reply_text(localized_message("status_not_found", language))
        return
    with SessionLocal() as db:
        ticket = get_ticket_by_code(db, normalized_code)
        if ticket is None:
            await message.reply_text(localized_message("status_not_found", language))
            return
        status = ticket.status
    await message.reply_text(
        localized_message(
            "status_update",
            language,
            ticket_code=normalized_code,
            status=_status_label(status, language),
        )
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return the current status for a ticket code or ask for one."""

    if update.message is None:
        return
    language = get_user_language(context.user_data)
    ticket_code = context.args[0] if context.args else None
    if ticket_code:
        await _send_status(update.message, ticket_code, language)
        return
    context.user_data["awaiting_status"] = True
    await update.message.reply_text(localized_message("status_prompt", language))


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Accept a citizen complaint and create or clarify its ticket."""

    if update.message is None or not update.message.text:
        return
    language = get_user_language(context.user_data)
    if context.user_data.pop("awaiting_status", False):
        await _send_status(update.message, update.message.text, language)
        return

    user_details = _telegram_user_details(update)
    if user_details is None:
        await update.message.reply_text(localized_message("error_generic", language))
        return
    telegram_id, name = user_details
    try:
        with SessionLocal() as db:
            user = upsert_telegram_user(
                db,
                telegram_id=telegram_id,
                name=name,
                language=language,
            )
            prepared = prepare_complaint(update.message.text, language)
            if prepared.needs_clarification:
                context.user_data["pending_complaint"] = {
                    "prepared": prepared.to_context(),
                    "user_id": user.id,
                }
                await update.message.reply_text(
                    f"{localized_message('clarification_prompt', language)}\n"
                    f"{localized_message('department_question', language)}",
                    reply_markup=department_keyboard(language),
                )
                return
            ticket = create_prepared_ticket(db, prepared=prepared, user_id=user.id)
    except (LookupError, ValueError, SQLAlchemyError):
        logger.exception("Unable to process Telegram complaint")
        await update.message.reply_text(localized_message("error_generic", language))
        return

    await update.message.reply_text(_ticket_confirmation(ticket, language))


async def department_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a ticket after the citizen resolves an ambiguous department."""

    query = update.callback_query
    if query is None:
        return
    await query.answer()
    language = get_user_language(context.user_data)
    code = (query.data or "").removeprefix(DEPARTMENT_CALLBACK_PREFIX).upper()
    pending = context.user_data.get("pending_complaint")
    if code not in DEPARTMENT_CODES or not isinstance(pending, dict):
        await query.edit_message_text(localized_message("error_generic", language))
        return

    try:
        prepared = PreparedComplaint.from_context(pending["prepared"])
        with SessionLocal() as db:
            ticket = create_prepared_ticket(
                db,
                prepared=prepared,
                user_id=int(pending["user_id"]),
                department_code=code,
            )
    except (KeyError, TypeError, ValueError, LookupError, SQLAlchemyError):
        logger.exception("Unable to create clarified Telegram complaint")
        await query.edit_message_text(localized_message("error_generic", language))
        return

    context.user_data.pop("pending_complaint", None)
    await query.edit_message_text(_ticket_confirmation(ticket, language))


def build_telegram_application(token: str | None = None) -> Application:
    """Create the Telegram application without making a network request."""

    bot_token = token or get_settings().telegram_bot_token
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required to start the Telegram bot")

    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CallbackQueryHandler(language_callback, pattern=r"^language:(en|hi|te)$"))
    application.add_handler(CallbackQueryHandler(department_callback, pattern=r"^department:[A-Z]+$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    return application


def run_telegram_bot(token: str | None = None) -> None:
    """Start polling Telegram updates using the configured bot token."""

    settings = get_settings()
    configure_logging(settings.log_level)
    scheduler = None
    try:
        initialize_database()
        with SessionLocal() as db:
            seed_departments(db)
        scheduler = start_background_scheduler()
        application = build_telegram_application(token)
        logger.info("Starting Telegram grievance bot; waiting for updates")
        application.run_polling()
    except ValueError as exc:
        logger.error("Telegram bot configuration error: %s", exc)
        raise SystemExit(2) from exc
    except InvalidToken as exc:
        logger.error("Telegram rejected TELEGRAM_BOT_TOKEN. Generate a new token with BotFather.")
        raise SystemExit(2) from exc
    except NetworkError as exc:
        logger.error("Unable to reach the Telegram API. Check internet or firewall settings: %s", exc)
        raise SystemExit(3) from exc
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


if __name__ == "__main__":
    run_telegram_bot()
