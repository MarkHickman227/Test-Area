from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.errors import AppError
from app.models.base import utcnow
from app.models.enums import AgeVerificationStatus, UserStatus
from app.models.user import AgeVerification, User
from app.services.audit import write_audit
from app.services.auth import grant_welcome_credits


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
            }
        user.age_verification_status = AgeVerificationStatus.PENDING
        self.db.commit()
        write_audit(
            self.db,
            action="age.session_created",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
        )
        self.db.commit()
        return {
            "status": AgeVerificationStatus.PENDING,
            "provider": self.settings.age_verification_provider,
            "sandbox": self.settings.allow_sandbox_age_verify,
            "handoff_url": f"{self.settings.app_base_url}/age-verification?sandbox=1",
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
        self.db.add(
            AgeVerification(
                user_id=user.id,
                provider=self.settings.age_verification_provider,
                provider_ref_encrypted=self.crypto.encrypt(provider_ref),
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
        if not self.settings.allow_sandbox_age_verify:
            raise AppError(
                "SANDBOX_DISABLED", "Sandbox age assurance is disabled.", 403
            )
        return self.apply_outcome(user, outcome, provider_ref=f"sandbox:{user.id}")
