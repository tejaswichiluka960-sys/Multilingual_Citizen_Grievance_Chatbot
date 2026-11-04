"""SQLAlchemy models for users, departments, tickets and audit history."""

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utc_now() -> datetime:
    """Return the current UTC time for database defaults."""

    return datetime.now(UTC)


class User(Base):
    """Citizen identity and preferred communication language."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    telegram_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(150))
    preferred_lang: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="user")


class UserSession(Base):
    """Database-backed browser session for a registered citizen."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[User] = relationship()


class Department(Base):
    """Department that receives routed grievance tickets."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    sla_hours: Mapped[float] = mapped_column(Float, default=48.0, nullable=False)
    escalation_contact: Mapped[str | None] = mapped_column(String(150))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="department")
    admin_users: Mapped[list["AdminUser"]] = relationship(back_populates="department")


class Ticket(Base):
    """Citizen grievance ticket and its current routing state."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="NEW", index=True, nullable=False)
    location_text: Mapped[str | None] = mapped_column(String(300))
    incident_date: Mapped[date | None] = mapped_column(Date)
    incident_time: Mapped[time | None] = mapped_column(Time)
    source_channel: Mapped[str] = mapped_column(String(30), default="telegram", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="tickets")
    department: Mapped[Department | None] = relationship(back_populates="tickets")
    events: Mapped[list["TicketEvent"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketEvent.created_at",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
    )


class TicketEvent(Base):
    """Immutable status or officer-note event for a ticket."""

    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="events")


class Notification(Base):
    """Citizen notification delivery record."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(30), default="telegram", nullable=False)
    recipient: Mapped[str] = mapped_column(String(150), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="notifications")


class AdminUser(Base):
    """Officer account used to access the admin dashboard."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default="officer", nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    department: Mapped[Department | None] = relationship(back_populates="admin_users")


class AuditLog(Base):
    """Audit record for administrative and system actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
