from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, new_uuid


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    max_images_per_job: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    priority_multiplier: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allows_priority: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    hourly_job_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    monthly_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    description: Mapped[str] = mapped_column(String(240), nullable=False, default="")


class CreditLedger(Base, TimestampMixin):
    __tablename__ = "credit_ledger"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CREDIT")
    related_job_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("generation_jobs.id")
    )
    related_payment_id: Mapped[Optional[str]] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"))


class PaymentTransaction(Base, TimestampMixin):
    __tablename__ = "payment_transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    provider_ref: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="GBP")
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
