"""Initial multilingual grievance classifier with deterministic fallbacks."""

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.services.hf_classifier import HuggingFaceClassifier
from app.services.language_detection import (
    LANGUAGE_UNKNOWN,
    detect_language,
    normalize_text,
)

logger = logging.getLogger(__name__)

DEPARTMENT_MARKERS: dict[str, tuple[str, ...]] = {
    "WATER": (
        "water",
        "pani",
        "neellu",
        "నీరు",
        "నీటి",
        "పానీ",
        "पानी",
        "जल",
        "leak",
        "drainage",
        "sewer",
        "सीवर",
        "డ్రైనేజీ",
    ),
    "POWER": (
        "electricity",
        "power",
        "bijli",
        "current",
        "wire",
        "pole",
        "spark",
        "light",
        "lights",
        "street light",
        "street lights",
        "streetlight",
        "streetlights",
        "lamp",
        "lamps",
        "విద్యుత్",
        "కరెంట్",
        "తీగ",
        "बिजली",
        "तार",
    ),
    "ROADS": (
        "road",
        "pothole",
        "sadak",
        "gunthalu",
        "गड्ढा",
        "सड़क",
        "రోడ్డు",
        "గుంత",
        "వీధి",
    ),
    "SANITATION": (
        "garbage",
        "waste",
        "sanitation",
        "kachra",
        "safai",
        "chetta",
        "dumping",
        "कचरा",
        "सफाई",
        "చెత్త",
        "పారిశుధ్యం",
    ),
    "POLICE": (
        "police",
        "safety",
        "theft",
        "harassment",
        "threat",
        "crime",
        "పోలీసు",
        "భద్రత",
        "దొంగతనం",
        "पुलिस",
        "सुरक्षा",
        "चोरी",
    ),
    "HEALTH": (
        "health",
        "hospital",
        "doctor",
        "clinic",
        "medicine",
        "ఆరోగ్యం",
        "ఆసుపత్రి",
        "వైద్యుడు",
        "स्वास्थ्य",
        "अस्पताल",
        "डॉक्टर",
    ),
    "EDUCATION": (
        "school",
        "college",
        "education",
        "student",
        "teacher",
        "పాఠశాల",
        "విద్య",
        "విద్యార్థి",
        "स्कूल",
        "शिक्षा",
        "छात्र",
    ),
    "TRANSPORT": (
        "bus",
        "transport",
        "route",
        "train",
        "ticket",
        "బస్సు",
        "రవాణా",
        "మార్గం",
        "बस",
        "परिवहन",
        "मार्ग",
    ),
    "REVENUE": (
        "land",
        "property",
        "certificate",
        "document",
        "record",
        "revenue",
        "bhumi",
        "భూమి",
        "ధృవపత్రం",
        "రికార్డు",
        "भूमि",
        "प्रमाणपत्र",
        "रिकॉर्ड",
    ),
}

_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?|[\u0900-\u097F]+|[\u0C00-\u0C7F]+")

DEPARTMENT_INTENTS = {
    "WATER": "water_supply",
    "POWER": "electricity",
    "ROADS": "roads_infrastructure",
    "SANITATION": "solid_waste",
    "POLICE": "public_safety",
    "HEALTH": "health_service",
    "EDUCATION": "education_service",
    "TRANSPORT": "public_transport",
    "REVENUE": "land_certificates",
    "OTHER": "human_review",
}

HIGH_PRIORITY_MARKERS = (
    "urgent",
    "emergency",
    "immediate",
    "fire",
    "shock",
    "accident",
    "danger",
    "threat",
    "harassment",
    "sparking",
    "exposed wire",
    "no water for days",
    "several days",
    "तुरंत",
    "आपात",
    "अत्यावश्यक",
    "दिनों से",
    "అత్యవసరం",
    "వెంటనే",
    "రోజులుగా",
)

LOW_PRIORITY_MARKERS = (
    "information",
    "enquiry",
    "status",
    "certificate",
    "application",
    "जानकारी",
    "प्रमाणपत्र",
    "సమాచారం",
    "ధృవపత్రం",
)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Department and priority classification returned to the workflow."""

    language: str
    department: str
    intent: str
    priority: str
    confidence: float
    matched_terms: tuple[str, ...]
    needs_clarification: bool
    model: str = "keyword-v1"


@lru_cache(maxsize=1)
def _get_hugging_face_classifier() -> HuggingFaceClassifier | None:
    """Return the lazy ML classifier when a saved bundle is available."""

    settings = get_settings()
    if not settings.enable_ml_classifier or not Path(settings.classifier_model_path).exists():
        return None
    return HuggingFaceClassifier(settings.classifier_model_path, settings.embedding_model)


def _marker_present(text: str, marker: str, tokens: set[str]) -> bool:
    """Match a Unicode term, phrase or Roman-script token."""

    normalized_marker = marker.lower()
    if " " in normalized_marker:
        return normalized_marker in text
    return normalized_marker in tokens


def _department_scores(text: str) -> dict[str, list[str]]:
    """Return matched department markers grouped by department."""

    tokens = {token.lower() for token in _WORD_PATTERN.findall(text)}
    return {
        department: [marker for marker in markers if _marker_present(text, marker, tokens)]
        for department, markers in DEPARTMENT_MARKERS.items()
    }


def _classify_priority(text: str) -> tuple[str, tuple[str, ...]]:
    """Classify urgency independently of department."""

    tokens = {token.lower() for token in _WORD_PATTERN.findall(text)}
    high_hits = tuple(marker for marker in HIGH_PRIORITY_MARKERS if _marker_present(text, marker, tokens))
    if high_hits:
        return "high", high_hits
    low_hits = tuple(marker for marker in LOW_PRIORITY_MARKERS if _marker_present(text, marker, tokens))
    if low_hits:
        return "low", low_hits
    return "medium", ()


def classify_text(text: str, confidence_threshold: float | None = None) -> ClassificationResult:
    """Classify a complaint using multilingual keyword evidence."""

    normalized = normalize_text(text).lower()
    language_result = detect_language(normalized)
    department_matches = _department_scores(normalized)
    ranked = sorted(
        ((department, markers) for department, markers in department_matches.items() if markers),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    top_department = ranked[0][0] if ranked else "OTHER"
    top_matches = ranked[0][1] if ranked else []
    second_score = len(ranked[1][1]) if len(ranked) > 1 else 0
    top_score = len(top_matches)

    if not ranked:
        confidence = 0.15
    else:
        confidence = 0.45 + min(top_score, 3) * 0.12 + min(max(top_score - second_score, 0), 3) * 0.08
        if top_score == second_score:
            confidence -= 0.15
        confidence = min(0.98, max(0.2, confidence))

    priority, priority_hits = _classify_priority(normalized)
    threshold = get_settings().classification_confidence_threshold if confidence_threshold is None else confidence_threshold
    needs_clarification = top_department == "OTHER" or confidence < threshold
    matched_terms = tuple(top_matches) + tuple(priority_hits)

    result = ClassificationResult(
        language=language_result.language if language_result.language != LANGUAGE_UNKNOWN else LANGUAGE_UNKNOWN,
        department=top_department,
        intent=DEPARTMENT_INTENTS[top_department],
        priority=priority,
        confidence=round(confidence, 3),
        matched_terms=matched_terms,
        needs_clarification=needs_clarification,
    )

    model = _get_hugging_face_classifier()
    if model is None:
        return result
    try:
        prediction = model.predict(normalized)
    except Exception:
        logger.exception("Hugging Face classifier failed; using keyword fallback")
        return result

    model_confidence = prediction.department_confidence
    # Preserve a strong deterministic match for common, explicit complaints.
    # The ML model remains active for less explicit or multilingual cases, but
    # it must not turn an unambiguous keyword match into a clarification flow.
    keyword_is_confident = result.department != "OTHER" and result.confidence >= threshold
    model_department = (
        result.department
        if keyword_is_confident
        else prediction.department if model_confidence >= threshold else result.department
    )
    model_priority = prediction.priority
    if result.priority == "high":
        model_priority = "high"
    model_needs_clarification = (
        False
        if keyword_is_confident
        else model_department == "OTHER" or model_confidence < threshold
    )
    final_confidence = result.confidence if keyword_is_confident else model_confidence
    return ClassificationResult(
        language=result.language,
        department=model_department,
        intent=DEPARTMENT_INTENTS.get(model_department, "human_review"),
        priority=model_priority,
        confidence=round(final_confidence, 3),
        matched_terms=result.matched_terms + (f"model:{prediction.model_name}",),
        needs_clarification=model_needs_clarification,
        model=prediction.model_name,
    )
