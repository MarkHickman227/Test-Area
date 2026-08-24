from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class ModerationEvent(Base, TimestampMixin):
    __tablename__ = "moderation_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id"))
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_hits: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    classifier_score: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    reporter_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id"))
    output_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generation_outputs.id")
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    outcome: Mapped[Optional[str]] = mapped_column(String(64))
    evidence_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)


class EnforcementAction(Base, TimestampMixin):
    __tablename__ = "enforcement_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id"))
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    preserve_evidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36))
    actor_role: Mapped[Optional[str]] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[Optional[str]] = mapped_column(String(64))
    request_id: Mapped[Optional[str]] = mapped_column(String(64))
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
