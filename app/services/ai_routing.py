"""Sarvam AI routing for free-form multilingual complaints."""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

AI_DEPARTMENT_INTENTS = {
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
AI_DEPARTMENT_CODES = tuple(AI_DEPARTMENT_INTENTS)
AI_PRIORITIES = ("low", "medium", "high")


class AIRoutingError(RuntimeError):
    """Raised when Sarvam returns an unusable routing decision."""


@dataclass(frozen=True, slots=True)
class AIRoutingDecision:
    """Validated routing data returned by the external AI provider."""

    department: str
    intent: str
    priority: str
    confidence: float
    needs_clarification: bool
    summary: str


def _response_schema() -> dict[str, Any]:
    """Return the strict JSON schema sent to Sarvam."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "grievance_routing",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "department_code": {
                        "type": "string",
                        "enum": list(AI_DEPARTMENT_CODES),
                    },
                    "intent": {"type": "string"},
                    "priority": {"type": "string", "enum": list(AI_PRIORITIES)},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "needs_clarification": {"type": "boolean"},
                    "summary": {"type": "string"},
                },
                "required": [
                    "department_code",
                    "intent",
                    "priority",
                    "confidence",
                    "needs_clarification",
                    "summary",
                ],
                "additionalProperties": False,
            },
        },
    }


def _system_prompt() -> str:
    """Return the routing policy used to constrain the AI."""

    departments = ", ".join(AI_DEPARTMENT_CODES)
    return (
        "You are the routing classifier for a government citizen grievance system. "
        "Classify the citizen's complaint; do not answer it and do not invent a department. "
        f"Use exactly one department_code from: {departments}. "
        "Understand English, Hindi, Telugu, Hinglish, Tenglish, and code-mixed text. "
        "Use OTHER when the complaint is outside these services or genuinely ambiguous. "
        "Set needs_clarification=true for OTHER or when the department cannot be determined. "
        "Use high priority only for immediate safety, health, fire, exposed electrical, crime, "
        "or similarly urgent situations. Return only the requested JSON object."
    )


def _parse_content(content: Any) -> dict[str, Any]:
    """Parse structured JSON content from a Sarvam response."""

    if not isinstance(content, str) or not content.strip():
        raise AIRoutingError("Sarvam returned empty routing content")
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIRoutingError("Sarvam returned invalid routing JSON") from exc
    if not isinstance(parsed, dict):
        raise AIRoutingError("Sarvam routing response must be a JSON object")
    return parsed


def _validate_decision(payload: dict[str, Any]) -> AIRoutingDecision:
    """Validate model output against application routing rules."""

    department = str(payload.get("department_code", "")).strip().upper()
    if department not in AI_DEPARTMENT_CODES:
        raise AIRoutingError("Sarvam returned an unknown department")
    priority = str(payload.get("priority", "")).strip().lower()
    if priority not in AI_PRIORITIES:
        raise AIRoutingError("Sarvam returned an unknown priority")
    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise AIRoutingError("Sarvam returned an invalid confidence") from exc
    if not 0.0 <= confidence <= 1.0:
        raise AIRoutingError("Sarvam confidence is outside the valid range")
    intent = str(payload.get("intent") or AI_DEPARTMENT_INTENTS[department]).strip()[:100]
    summary = str(payload.get("summary") or "").strip()[:500]
    needs_clarification = bool(payload.get("needs_clarification")) or department == "OTHER"
    return AIRoutingDecision(
        department=department,
        intent=intent or AI_DEPARTMENT_INTENTS[department],
        priority=priority,
        confidence=confidence,
        needs_clarification=needs_clarification,
        summary=summary,
    )


class SarvamAIRouter:
    """Small synchronous Sarvam client with injectable transport for tests."""

    def __init__(
        self,
        settings: Settings | None = None,
        requester: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._requester = requester

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._requester is not None:
            return self._requester(payload)
        if not self.settings.sarvam_api_key:
            raise AIRoutingError("SARVAM_API_KEY is not configured")
        headers = {
            "api-subscription-key": self.settings.sarvam_api_key,
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self.settings.ai_routing_timeout_seconds) as client:
                response = client.post(self.settings.sarvam_api_url, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            error_code = None
            try:
                error_body = exc.response.json()
                error_code = error_body.get("error", {}).get("code")
            except (ValueError, AttributeError):
                pass
            logger.warning(
                "Sarvam routing returned HTTP %s (%s)",
                exc.response.status_code,
                error_code or "unknown_error",
            )
            if error_code == "invalid_api_key_error":
                raise AIRoutingError("Sarvam API key is invalid or inactive") from exc
            raise AIRoutingError("Sarvam routing request was rejected") from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Sarvam routing request failed: %s", type(exc).__name__)
            raise AIRoutingError("Sarvam routing request failed") from exc
        if not isinstance(body, dict):
            raise AIRoutingError("Sarvam response was not a JSON object")
        return body

    def classify(self, text: str, language: str) -> AIRoutingDecision:
        """Classify one complaint into a validated project department."""

        payload = {
            "model": self.settings.sarvam_model,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {
                    "role": "user",
                    "content": f"Selected language: {language}\nCitizen complaint:\n{text}",
                },
            ],
            "temperature": 0,
            "max_tokens": 300,
            "reasoning_effort": None,
            "response_format": _response_schema(),
        }
        body = self._request(payload)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIRoutingError("Sarvam response did not contain a chat message") from exc
        return _validate_decision(_parse_content(content))


@lru_cache(maxsize=1)
def get_ai_router() -> SarvamAIRouter | None:
    """Return the configured AI router, or None for local-only mode."""

    settings = get_settings()
    if not settings.enable_ai_routing or not settings.sarvam_api_key:
        return None
    return SarvamAIRouter(settings)
