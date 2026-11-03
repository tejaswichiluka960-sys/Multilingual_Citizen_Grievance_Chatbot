"""Tests for the initial multilingual classifier baseline."""

import pytest

from app.services.classifier import classify_text


@pytest.mark.parametrize(
    ("text", "department"),
    (
        ("There is no water supply near my street", "WATER"),
        ("Street lights are not working in my area", "POWER"),
        ("मेरे इलाके में बिजली नहीं है", "POWER"),
        ("మా వీధిలో రోడ్డు గుంతలు ఉన్నాయి", "ROADS"),
        ("Mere area mein kachra collect nahi hua", "SANITATION"),
        ("Ma area lo police safety problem undi", "POLICE"),
        ("The hospital has no doctor", "HEALTH"),
        ("The school has no teacher", "EDUCATION"),
        ("Bus route is not available", "TRANSPORT"),
        ("भूमि रिकॉर्ड में सुधार चाहिए", "REVENUE"),
    ),
)
def test_classifies_supported_departments(text: str, department: str) -> None:
    result = classify_text(text)

    assert result.department == department
    assert result.intent != "human_review"
    assert result.confidence >= 0.55
    assert result.needs_clarification is False


def test_classifies_urgent_priority() -> None:
    result = classify_text("Exposed electric wire is sparking near the school, urgent help needed")

    assert result.department == "POWER"
    assert result.priority == "high"
    assert "sparking" in result.matched_terms


def test_classifies_low_priority_information_request() -> None:
    result = classify_text("Please provide information about a land certificate")

    assert result.department == "REVENUE"
    assert result.priority == "low"


def test_low_confidence_message_requests_clarification() -> None:
    result = classify_text("Please help with this problem")

    assert result.department == "OTHER"
    assert result.intent == "human_review"
    assert result.needs_clarification is True
    assert result.confidence < 0.55


def test_high_confidence_can_be_configured_with_threshold() -> None:
    result = classify_text("Water leak near the market", confidence_threshold=0.9)

    assert result.department == "WATER"
    assert result.needs_clarification is True
