"""Tests for safe Sarvam AI complaint routing."""

import json

import pytest

from app.config import Settings
from app.services.ai_routing import AIRoutingError, SarvamAIRouter


def test_sarvam_router_validates_structured_decision() -> None:
    def requester(payload):
        assert payload["model"] == "sarvam-105b"
        assert payload["response_format"]["type"] == "json_schema"
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "department_code": "WATER",
                                "intent": "water_supply",
                                "priority": "high",
                                "confidence": 0.92,
                                "needs_clarification": False,
                                "summary": "No water supply in the area",
                            }
                        )
                    }
                }
            ]
        }

    router = SarvamAIRouter(Settings(sarvam_api_key="test-key"), requester=requester)
    result = router.classify("మా ప్రాంతంలో నీరు రావడం లేదు", "te")

    assert result.department == "WATER"
    assert result.priority == "high"
    assert result.confidence == 0.92


def test_sarvam_router_rejects_unknown_department() -> None:
    router = SarvamAIRouter(
        Settings(),
        requester=lambda payload: {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "department_code": "RANDOM",
                                "intent": "unknown",
                                "priority": "medium",
                                "confidence": 0.9,
                                "needs_clarification": False,
                                "summary": "Unknown",
                            }
                        )
                    }
                }
            ]
        },
    )

    with pytest.raises(AIRoutingError, match="unknown department"):
        router.classify("Some complaint", "en")
