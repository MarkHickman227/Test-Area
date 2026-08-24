from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid, utcnow, ensure_aware
from app.models.enums import AgeVerificationStatus, UserRole, UserStatus


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserStatus.PENDING_EMAIL_VERIFICATION
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.USER)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    age_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    age_verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AgeVerificationStatus.NOT_STARTED
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    mfa_secret_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(80))
    plan_id: Mapped[str] = mapped_column(String(64), nullable=False, default="standard")
    country_code: Mapped[Optional[str]] = mapped_column(String(8))
    invite_code: Mapped[Optional[str]] = mapped_column(String(64))
    blocked_prompt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    identities: Mapped[list["AuthIdentity"]] = relationship(back_populates="user")


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    preferred_aspect_ratio: Mapped[str] = mapped_column(String(16), default="2:3")
    preferred_model_profile_id: Mapped[Optional[str]] = mapped_column(String(64))
    locale: Mapped[str] = mapped_column(String(16), default="en-GB")


class AuthIdentity(Base, TimestampMixin):
    __tablename__ = "auth_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_subject"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    user: Mapped[User] = relationship(back_populates="identities")


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent_hash: Mapped[Optional[str]] = mapped_column(String(64))
    mfa_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user: Mapped[User] = relationship(back_populates="sessions")

    @property
    def is_active(self) -> bool:
        now = utcnow()
        expires = ensure_aware(self.expires_at)
        revoked = ensure_aware(self.revoked_at)
        return revoked is None and expires is not None and expires > now


class EmailToken(Base, TimestampMixin):
    __tablename__ = "email_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class AgeVerification(Base, TimestampMixin):
    __tablename__ = "age_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_ref_encrypted: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    provider_ref_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    assurance_level: Mapped[Optional[str]] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_payload_retained: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )


class ConsentAcceptance(Base, TimestampMixin):
    __tablename__ = "consent_acceptances"
    __table_args__ = (UniqueConstraint("user_id", "document_type", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64))
