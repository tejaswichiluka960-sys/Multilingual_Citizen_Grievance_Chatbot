"""Tests for the classifier inspection API route."""

from app.api.classify import classify_route
from app.schemas import ClassificationRequest
from app.services import classifier


def test_classify_route_returns_routing_data(monkeypatch) -> None:
    """Classification inspection returns routing data without persistence."""

    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    response = classify_route(
        ClassificationRequest(text="There is no water supply near my street")
    )

    assert response.department == "WATER"
    assert response.intent == "water_supply"
    assert response.needs_clarification is False
    assert response.matched_terms


def test_classify_route_keeps_ambiguous_complaints_for_review(monkeypatch) -> None:
    """Low-confidence complaints remain eligible for clarification."""

    monkeypatch.setattr(classifier, "_get_hugging_face_classifier", lambda: None)
    monkeypatch.setattr(classifier, "get_ai_router", lambda: None)
    response = classify_route(ClassificationRequest(text="Please help with this problem"))

    assert response.department == "OTHER"
    assert response.needs_clarification is True
