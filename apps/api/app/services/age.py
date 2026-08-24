from __future__ import annotations

import hashlib
import hmac
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.age.factory import make_age_provider
from app.config import Settings
from app.crypto import CryptoService
from app.errors import AppError
from app.models.base import utcnow
from app.models.enums import AgeVerificationStatus, UserStatus
from app.models.user import AgeVerification, User
from app.services.audit import write_audit
from app.services.auth import grant_welcome_credits

IDENTITY_KEYS = {
    "date_of_birth",
    "dob",
    "birthdate",
    "document",
    "document_image",
    "selfie",
    "id_image",
    "full_name",
    "address",
}


def provider_ref_hash(ref: str) -> str:
    return hashlib.sha256(ref.encode()).hexdigest()


class AgeVerificationService:
    def __init__(self, db: Session, settings: Settings, crypto: CryptoService) -> None:
        self.db = db
        self.settings = settings
        self.crypto = crypto

    def create_session(self, user: User) -> dict:
        if user.status == UserStatus.PENDING_EMAIL_VERIFICATION:
            raise AppError(
                "EMAIL_UNVERIFIED", "Verify your email before age assurance.", 403
            )
        if user.age_verification_status == AgeVerificationStatus.PASSED:
            return {
                "status": AgeVerificationStatus.PASSED,
                "provider": self.settings.age_verification_provider,
                "sandbox": False,
            }
        session = make_age_provider(self.settings).create_session(user)
        user.age_verification_status = AgeVerificationStatus.PENDING
        self.db.add(
            AgeVerification(
                user_id=user.id,
                provider=self.settings.age_verification_provider,
                provider_ref_encrypted=self.crypto.encrypt(session.session_id),
                provider_ref_hash=provider_ref_hash(session.session_id),
                assurance_level=None,
                outcome=AgeVerificationStatus.PENDING.value,
                raw_payload_retained=False,
            )
        )
        write_audit(
            self.db,
            action="age.session_created",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
            metadata={"provider": self.settings.age_verification_provider},
        )
        self.db.commit()
        return {
            "status": AgeVerificationStatus.PENDING,
            "provider": self.settings.age_verification_provider,
            "sandbox": session.sandbox,
            "handoff_url": session.handoff_url,
        }

    def apply_outcome(
        self,
        user: User,
        outcome: str,
        provider_ref: str,
        assurance_level: str = "high",
    ) -> User:
        allowed = {
            "PASSED": AgeVerificationStatus.PASSED,
            "FAILED": AgeVerificationStatus.FAILED,
            "INCONCLUSIVE": AgeVerificationStatus.INCONCLUSIVE,
        }
        if outcome not in allowed:
            raise AppError("INVALID_OUTCOME", "Unknown age-verification outcome.")
        status = allowed[outcome]
        ref_hash = provider_ref_hash(provider_ref)
        existing = self.db.scalar(
            select(AgeVerification).where(
                AgeVerification.provider_ref_hash == ref_hash,
                AgeVerification.outcome == status.value,
            )
        )
        if existing and user.age_verification_status == status.value:
            return user
        if (
            user.age_verification_status == AgeVerificationStatus.PASSED
            and status != AgeVerificationStatus.PASSED
        ):
            write_audit(
                self.db,
                action="age.outcome_ignored",
                target_type="user",
                target_id=user.id,
                metadata={"ignored": status.value},
            )
            self.db.commit()
            return user
        self.db.add(
            AgeVerification(
                user_id=user.id,
                provider=self.settings.age_verification_provider,
                provider_ref_encrypted=self.crypto.encrypt(provider_ref),
                provider_ref_hash=ref_hash,
                assurance_level=assurance_level,
                outcome=status.value,
                raw_payload_retained=False,
            )
        )
        user.age_verification_status = status.value
        if status == AgeVerificationStatus.PASSED:
            user.age_verified_at = utcnow()
            if user.status == UserStatus.PENDING_AGE_VERIFICATION:
                user.status = UserStatus.ACTIVE
            grant_welcome_credits(self.db, user, self.settings)
        write_audit(
            self.db,
            action="age.outcome",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
            metadata={"outcome": status.value, "assurance_level": assurance_level},
        )
        self.db.commit()
        return user

    def sandbox_complete(self, user: User, outcome: str = "PASSED") -> User:
        if not self.settings.sandbox_age_allowed:
            raise AppError(
                "SANDBOX_DISABLED", "Sandbox age assurance is disabled.", 403
            )
        return self.apply_outcome(user, outcome, provider_ref=f"sandbox:{user.id}")

    def handle_webhook(self, raw: bytes, signature: str | None) -> dict:
        self._verify_hmac(raw, signature)
        body = _parse_json(raw)
        for key in IDENTITY_KEYS:
            body.pop(key, None)
        provider_ref = str(
            body.get("provider_ref") or body.get("session_id") or "webhook"
        )
        user = self._find_user(body, provider_ref)
        if not user:
            raise AppError(
                "USER_NOT_FOUND", "Unknown user for age-verification webhook.", 404
            )
        self.apply_outcome(
            user,
            str(body.get("outcome") or "FAILED"),
            provider_ref=provider_ref,
            assurance_level=str(body.get("assurance_level") or "high"),
        )
        return {"ok": True, "status": user.age_verification_status}

    def _find_user(self, body: dict, provider_ref: str) -> User | None:
        user_id = body.get("user_id")
        if user_id:
            return self.db.get(User, user_id)
        hashed = provider_ref_hash(provider_ref)
        row = self.db.scalar(
            select(AgeVerification)
            .where(AgeVerification.provider_ref_hash == hashed)
            .order_by(AgeVerification.created_at.desc())
        )
        if not row:
            return None
        return self.db.get(User, row.user_id)

    def _verify_hmac(self, raw: bytes, header: str | None) -> None:
        expected = hmac.new(
            self.settings.age_verification_webhook_secret.encode(),
            raw,
            "sha256",
        ).hexdigest()
        provided = (header or "").removeprefix("sha256=")
        try:
            valid = bool(provided) and hmac.compare_digest(expected, provided)
        except ValueError:
            valid = False
        if not valid:
            raise AppError("WEBHOOK_INVALID", "Webhook signature was not valid.", 401)


def _parse_json(raw: bytes) -> dict:
    try:
        body = json.loads(raw.decode() if raw else "{}")
    except json.JSONDecodeError as exc:
        raise AppError(
            "WEBHOOK_INVALID", "Webhook payload was not valid JSON.", 400
        ) from exc
    if not isinstance(body, dict):
        raise AppError("WEBHOOK_INVALID", "Webhook payload was not valid JSON.", 400)
    return body
