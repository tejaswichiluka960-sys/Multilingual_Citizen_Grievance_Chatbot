"""Classifier inspection endpoint for API clients and demonstrations."""

from fastapi import APIRouter

from app.schemas import ClassificationRequest, ClassificationResponse
from app.services.classifier import classify_text

router = APIRouter(tags=["classification"])


@router.post("/classify", response_model=ClassificationResponse)
def classify_route(payload: ClassificationRequest) -> ClassificationResponse:
    """Classify a complaint without persisting a ticket."""

    result = classify_text(payload.text, use_ai=True)
    return ClassificationResponse(
        language=result.language,
        department=result.department,
        intent=result.intent,
        priority=result.priority,
        confidence=result.confidence,
        matched_terms=list(result.matched_terms),
        needs_clarification=result.needs_clarification,
        model=result.model,
    )
