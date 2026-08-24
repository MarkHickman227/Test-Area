from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid
from app.models.enums import (
    JobStatus,
    ModerationState,
    PolicyDecision,
    QueueClass,
    ScanStatus,
    Visibility,
)


class ModelProfile(Base, TimestampMixin):
    __tablename__ = "model_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workflow_template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    base_credit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    allowed_resolutions: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class StylePreset(Base, TimestampMixin):
    __tablename__ = "style_presets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_profile_id: Mapped[str] = mapped_column(
        ForeignKey("model_profiles.id"), nullable=False
    )
    values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WorkflowTemplate(Base, TimestampMixin):
    __tablename__ = "workflow_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    compatible_model_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_policy_requirement_level: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    cost_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GenerationJob(Base, TimestampMixin):
    __tablename__ = "generation_jobs"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobStatus.VALIDATING
    )
    workflow_template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_profile_id: Mapped[str] = mapped_column(String(64), nullable=False)
    style_preset_id: Mapped[Optional[str]] = mapped_column(String(64))
    prompt_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    negative_prompt_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False)
    parameters_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    seed: Mapped[Optional[int]] = mapped_column(BigInteger)
    image_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing_rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    reservation_ledger_event_id: Mapped[Optional[str]] = mapped_column(String(36))
    policy_decision: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PolicyDecision.ALLOW
    )
    policy_score: Mapped[Optional[float]] = mapped_column(Float)
    moderation_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ModerationState.NONE
    )
    queue_class: Mapped[str] = mapped_column(
        String(32), nullable=False, default=QueueClass.STANDARD
    )
    worker_id: Mapped[Optional[str]] = mapped_column(String(128))
    comfy_prompt_id: Mapped[Optional[str]] = mapped_column(String(128))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[Optional[str]] = mapped_column(String(64))
    failure_detail: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class GenerationOutput(Base, TimestampMixin):
    __tablename__ = "generation_outputs"
    __table_args__ = (UniqueConstraint("job_id", "sequence_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("generation_jobs.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    original_storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_scan_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ScanStatus.PENDING
    )
    visibility: Mapped[str] = mapped_column(
        String(32), nullable=False, default=Visibility.PRIVATE
    )
    favourite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
