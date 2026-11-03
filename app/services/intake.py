"""Complaint intake orchestration shared by citizen-facing interfaces."""

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Department, Ticket, User
from app.services.classifier import ClassificationResult, classify_text
from app.services.language_detection import LANGUAGE_UNKNOWN, detect_language
from app.services.tickets import create_ticket
from app.services.translation import TranslationResult, get_translation_service


@dataclass(frozen=True, slots=True)
class PreparedComplaint:
    """Normalized complaint data ready for routing or clarification."""

    original_text: str
    language: str
    translated_text: str
    intent: str
    priority: str
    confidence: float
    department_code: str
    needs_clarification: bool

    def to_context(self) -> dict[str, object]:
        """Return a JSON-like representation safe for Telegram user state."""

        return asdict(self)

    @classmethod
    def from_context(cls, value: dict[str, object]) -> "PreparedComplaint":
        """Restore a prepared complaint from Telegram user state."""

        return cls(
            original_text=str(value["original_text"]),
            language=str(value["language"]),
            translated_text=str(value["translated_text"]),
            intent=str(value["intent"]),
            priority=str(value["priority"]),
            confidence=float(value["confidence"]),
            department_code=str(value["department_code"]),
            needs_clarification=bool(value["needs_clarification"]),
        )


def prepare_complaint(text: str, selected_language: str) -> PreparedComplaint:
    """Detect, classify and translate a complaint before database writes."""

    detection = detect_language(text)
    normalized_text = detection.normalized_text
    classification: ClassificationResult = classify_text(normalized_text)
    language = detection.language if detection.language != LANGUAGE_UNKNOWN else selected_language
    translation: TranslationResult = get_translation_service().translate_for_officer(
        normalized_text,
        language,
    )
    return PreparedComplaint(
        original_text=normalized_text,
        language=language,
        translated_text=translation.text,
        intent=classification.intent,
        priority=classification.priority,
        confidence=classification.confidence,
        department_code=classification.department,
        needs_clarification=classification.needs_clarification,
    )


def upsert_telegram_user(
    db: Session,
    *,
    telegram_id: str,
    name: str | None,
    language: str,
) -> User:
    """Create or update the citizen record associated with a Telegram user."""

    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(telegram_id=telegram_id, name=name, preferred_lang=language)
        db.add(user)
    else:
        user.name = name or user.name
        user.preferred_lang = language
    db.commit()
    db.refresh(user)
    return user


def create_prepared_ticket(
    db: Session,
    *,
    prepared: PreparedComplaint,
    user_id: int | None,
    department_code: str | None = None,
    actor: str = "telegram-bot",
    source_channel: str = "telegram",
) -> Ticket:
    """Persist a prepared complaint, optionally overriding its department."""

    selected_code = (department_code or prepared.department_code).strip().upper()
    department = db.scalar(select(Department).where(Department.code == selected_code))
    if department is None or not department.active:
        raise LookupError(f"Active department not found: {selected_code}")
    return create_ticket(
        db,
        original_text=prepared.original_text,
        language=prepared.language,
        user_id=user_id,
        department_id=department.id,
        translated_text=prepared.translated_text,
        intent=prepared.intent,
        priority=prepared.priority,
        confidence=prepared.confidence,
        source_channel=source_channel,
        actor=actor,
    )
