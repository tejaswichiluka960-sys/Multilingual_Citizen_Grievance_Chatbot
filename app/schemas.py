"""Shared API schemas for system and ticket endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str
    service: str
    environment: str
    database: str
    database_status: str


class TicketCreateRequest(BaseModel):
    """Validated input for creating a grievance ticket."""

    original_text: str = Field(min_length=1, max_length=10_000)
    language: str = Field(min_length=1, max_length=20)
    user_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    translated_text: str | None = Field(default=None, max_length=20_000)
    intent: str | None = Field(default=None, max_length=100)
    priority: Literal["low", "medium", "high"] = "medium"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    location_text: str | None = Field(default=None, max_length=300)
    source_channel: str = Field(default="telegram", min_length=1, max_length=30)
    actor: str = Field(default="system", min_length=1, max_length=100)


class TicketStatusUpdateRequest(BaseModel):
    """Validated input for a ticket status transition."""

    new_status: Literal["NEW", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "ESCALATED", "CLOSED", "REOPENED"]
    actor: str = Field(default="system", min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=5_000)


class TicketEventResponse(BaseModel):
    """Public representation of a ticket history event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    old_status: str | None
    new_status: str
    note: str | None
    actor: str
    created_at: datetime


class TicketResponse(BaseModel):
    """Public representation of a grievance ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_code: str
    user_id: int | None
    department_id: int | None
    department_code: str | None
    department_name: str | None
    original_text: str
    language: str
    translated_text: str | None
    intent: str | None
    priority: str
    confidence: float | None
    status: str
    location_text: str | None
    source_channel: str
    created_at: datetime
    updated_at: datetime
    sla_due_at: datetime | None
    escalation_level: int
    events: list[TicketEventResponse] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Input accepted by the browser chat fallback."""

    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    message: str = Field(default="", max_length=10_000)
    language: str = Field(default="en", min_length=1, max_length=20)
    department_code: str | None = Field(default=None, min_length=1, max_length=30)


class ChatChoice(BaseModel):
    """Department choice returned when classification needs clarification."""

    code: str
    label: str


class ChatResponse(BaseModel):
    """Browser chat response and optional ticket metadata."""

    session_id: str
    language: str
    reply: str
    ticket_code: str | None = None
    department_code: str | None = None
    status: str | None = None
    choices: list[ChatChoice] = Field(default_factory=list)


class ClassificationRequest(BaseModel):
    """Input for the classifier inspection endpoint."""

    text: str = Field(min_length=1, max_length=10_000)


class ClassificationResponse(BaseModel):
    """Classifier output without creating a ticket."""

    language: str
    department: str
    intent: str
    priority: str
    confidence: float
    matched_terms: list[str]
    needs_clarification: bool
    model: str


class RegisterRequest(BaseModel):
    """Citizen registration input."""

    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=150)
    language: str = Field(min_length=2, max_length=5)


class LoginRequest(BaseModel):
    """Citizen login input."""

    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class VoiceTranscriptionResponse(BaseModel):
    """Transcribed voice content returned before complaint submission."""

    transcript: str
    detected_language: str | None = None
    provider: str
