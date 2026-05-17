from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (

    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def uuid_str() -> str:
    return str(uuid.uuid4())


def _get_embedding_dimensions() -> int:
    """Return the configured embedding vector dimension.

    Reads from settings so that changing EMBEDDING_DIMENSIONS in the
    environment (or .env) is sufficient — no code change required.
    The import is deferred to break circular imports at module load time.
    """
    from app.core.config import get_settings  # noqa: PLC0415
    return get_settings().embedding_dimensions


async def validate_embedding_dimensions(engine) -> None:  # type: ignore[type-arg]
    """Assert that the live DB vector column matches EMBEDDING_DIMENSIONS.

    Must be called once at application startup (after the engine is created
    but before the first request is served).  Raises RuntimeError if the
    dimensions diverge, preventing silent data corruption caused by trying
    to insert or compare vectors of the wrong size.

    The query is skipped when the table does not yet exist (fresh install
    before the first Alembic migration), so the check is idempotent.
    """
    from sqlalchemy import text  # noqa: PLC0415

    configured_dim = _get_embedding_dimensions()
    query = text(
        """
        SELECT COALESCE(
            (
                SELECT atttypmod
                FROM pg_attribute a
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'embeddings'
                  AND a.attname  = 'vector'
                  AND a.atttypmod > 0
            ),
            -1
        ) AS live_dim
        """
    )
    async with engine.connect() as conn:
        row = (await conn.execute(query)).one()
    live_dim: int = row.live_dim
    if live_dim == -1:
        # Table not yet created — nothing to validate.
        return
    if live_dim != configured_dim:
        raise RuntimeError(
            f"Embedding dimension mismatch: DB column is {live_dim}-dimensional "
            f"but EMBEDDING_DIMENSIONS is set to {configured_dim}. "
            "Run an Alembic migration to resize the column or update the env var."
        )


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    admin = "admin"
    responder = "responder"
    viewer = "viewer"


class Severity(str, enum.Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class IncidentStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"
    closed = "closed"


class LogLevel(str, enum.Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False, default=Role.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(back_populates="user")


class RefreshToken(TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_token_id: Mapped[str | None] = mapped_column(String(36))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class Incident(TimestampMixin, Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[Severity] = mapped_column(Enum(Severity, name="incident_severity"), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus, name="incident_status"), nullable=False, default=IncidentStatus.open
    )
    source: Mapped[str] = mapped_column(String(120), nullable=False, default="manual")
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    summary: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    incident_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    logs: Mapped[list[LogEntry]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    triage_reports: Mapped[list[TriageReport]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )


class LogEntry(TimestampMixin, Base):
    __tablename__ = "logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel, name="log_level"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    incident: Mapped[Incident] = relationship(back_populates="logs")


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uq_embeddings_owner"),
        Index("ix_embeddings_owner", "owner_type", "owner_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_type: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False)
    vector: Mapped[list[float]] = mapped_column(
        Vector(_get_embedding_dimensions()), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, default="incident")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class WebSocketSession(Base):
    __tablename__ = "websocket_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    client_host: Mapped[str | None] = mapped_column(String(128))
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TriageReport(TimestampMixin, Base):
    __tablename__ = "triage_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    recommendations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)

    incident: Mapped[Incident] = relationship(back_populates="triage_reports")

