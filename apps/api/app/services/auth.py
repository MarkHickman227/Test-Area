from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

import argon2
import pyotp
from fastapi import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.crypto import CryptoService
from app.errors import AppError
from app.models.base import utcnow, ensure_aware
from app.models.enums import (
    AgeVerificationStatus,
    PrivilegedRoles,
    UserRole,
    UserStatus,
)
from app.models.user import (
    ConsentAcceptance,
    EmailToken,
    Session as UserSession,
    User,
    UserProfile,
)
from app.services.audit import write_audit
from app.services.credits import grant_promotional
from app.services.mail import MailService, hash_optional, hash_token

hasher = argon2.PasswordHasher()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except argon2.exceptions.VerifyMismatchError:
        return False
    except argon2.exceptions.VerificationError:
        return False


class AuthService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        mail: MailService,
        crypto: CryptoService,
    ) -> None:
        self.db = db
        self.settings = settings
        self.mail = mail
        self.crypto = crypto

    def register(
        self,
        email: str,
        password: str,
        acceptances: dict[str, str],
        ip: str | None,
        request_id: str | None = None,
        invite_code: str | None = None,
        country_code: str | None = None,
    ) -> User:
        email_n = normalize_email(email)
        if self.db.scalar(select(User).where(User.email == email_n)):
            raise AppError(
                "EMAIL_IN_USE", "An account with this email already exists.", 409
            )
        if len(password) < 10:
            raise AppError("WEAK_PASSWORD", "Password must be at least 10 characters.")
        required = {
            "terms": self.settings.current_terms_version,
            "privacy": self.settings.current_privacy_version,
            "content_policy": self.settings.current_content_policy_version,
            "age_policy": self.settings.current_age_policy_version,
        }
        for key, version in required.items():
            if acceptances.get(key) != version:
                raise AppError(
                    "CONSENT_REQUIRED",
                    "You must accept the current terms, privacy notice, and content policy.",
                )
        from app.services.access import consume_invite

        invite = consume_invite(self.db, invite_code, self.settings)
        user = User(
            email=email_n,
            password_hash=hash_password(password),
            status=UserStatus.PENDING_EMAIL_VERIFICATION,
            role=UserRole.USER,
            age_verification_status=AgeVerificationStatus.NOT_STARTED,
            plan_id=self.settings.default_plan_id,
            country_code=country_code,
            invite_code=invite.code if invite else None,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserProfile(user_id=user.id))
        ip_hash = hash_optional(ip)
        for doc, version in required.items():
            self.db.add(
                ConsentAcceptance(
                    user_id=user.id,
                    document_type=doc,
                    version=version,
                    ip_hash=ip_hash,
                )
            )
        token = self._issue_email_token(user.id, "verify_email")
        self.mail.send(
            user.email,
            "Verify your PrivateCanvas email",
            f"Confirm your email: {self.settings.app_base_url}/verify-email?token={token}",
        )
        write_audit(
            self.db,
            action="user.registered",
            target_type="user",
            target_id=user.id,
            request_id=request_id,
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def verify_email(self, token: str) -> User:
        record = self._consume_token(token, "verify_email")
        user = self.db.get(User, record.user_id)
        if not user:
            raise AppError("USER_NOT_FOUND", "Account not found.", 404)
        user.email_verified_at = utcnow()
        if user.status == UserStatus.PENDING_EMAIL_VERIFICATION:
            user.status = UserStatus.PENDING_AGE_VERIFICATION
        write_audit(
            self.db, action="user.email_verified", target_type="user", target_id=user.id
        )
        self.db.commit()
        return user

    def login(
        self, email: str, password: str, ip: str | None, user_agent: str | None
    ) -> tuple[User, UserSession, str]:
        user = self.db.scalar(select(User).where(User.email == normalize_email(email)))
        if not user or not user.password_hash:
            raise AppError(
                "INVALID_CREDENTIALS", "Email or password is incorrect.", 401
            )
        if user.status in {UserStatus.BANNED, UserStatus.DELETED}:
            raise AppError("ACCOUNT_BLOCKED", "This account cannot sign in.", 403)
        if user.locked_until and ensure_aware(user.locked_until) > utcnow():
            raise AppError(
                "ACCOUNT_LOCKED", "Too many failed sign-in attempts. Try later.", 423
            )
        if not verify_password(user.password_hash, password):
            user.failed_login_count += 1
            if user.failed_login_count >= 8:
                user.locked_until = utcnow() + timedelta(minutes=15)
            self.db.commit()
            write_audit(
                self.db,
                action="auth.login_failed",
                target_type="user",
                target_id=user.id,
            )
            raise AppError(
                "INVALID_CREDENTIALS", "Email or password is incorrect.", 401
            )
        user.failed_login_count = 0
        user.locked_until = None
        raw, session = self._create_session(user, ip, user_agent)
        write_audit(
            self.db,
            action="auth.login_success",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
        )
        self.db.commit()
        return user, session, raw

    def logout(self, session: UserSession) -> None:
        session.revoked_at = utcnow()
        write_audit(
            self.db,
            action="auth.logout",
            target_type="session",
            target_id=session.id,
            actor_user_id=session.user_id,
        )
        self.db.commit()

    def request_password_reset(self, email: str) -> None:
        user = self.db.scalar(select(User).where(User.email == normalize_email(email)))
        if not user:
            return
        token = self._issue_email_token(user.id, "reset_password")
        self.mail.send(
            user.email,
            "Reset your PrivateCanvas password",
            f"Reset password: {self.settings.app_base_url}/reset-password?token={token}",
        )
        write_audit(
            self.db,
            action="auth.password_reset_requested",
            target_type="user",
            target_id=user.id,
        )
        self.db.commit()

    def reset_password(self, token: str, new_password: str) -> None:
        if len(new_password) < 10:
            raise AppError("WEAK_PASSWORD", "Password must be at least 10 characters.")
        record = self._consume_token(token, "reset_password")
        user = self.db.get(User, record.user_id)
        if not user:
            raise AppError("USER_NOT_FOUND", "Account not found.", 404)
        user.password_hash = hash_password(new_password)
        sessions = self.db.scalars(
            select(UserSession).where(UserSession.user_id == user.id)
        ).all()
        for sess in sessions:
            sess.revoked_at = utcnow()
        write_audit(
            self.db, action="auth.password_reset", target_type="user", target_id=user.id
        )
        self.db.commit()

    def setup_mfa(self, user: User) -> tuple[str, str]:
        secret = pyotp.random_base32()
        user.mfa_secret_encrypted = self.crypto.encrypt(secret)
        user.mfa_enabled = False
        uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="PrivateCanvas"
        )
        write_audit(
            self.db,
            action="auth.mfa_setup",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
        )
        self.db.commit()
        return secret, uri

    def verify_mfa(self, user: User, session: UserSession, code: str) -> None:
        if not user.mfa_secret_encrypted:
            raise AppError("MFA_NOT_STARTED", "MFA setup has not been started.")
        secret = self.crypto.decrypt(user.mfa_secret_encrypted)
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise AppError("MFA_INVALID", "That authentication code is not valid.", 401)
        user.mfa_enabled = True
        session.mfa_completed = True
        write_audit(
            self.db,
            action="auth.mfa_verified",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
            actor_role=user.role,
        )
        self.db.commit()

    def attach_session_cookies(
        self, response: Response, raw_token: str, csrf: str
    ) -> None:
        response.set_cookie(
            self.settings.session_cookie_name,
            raw_token,
            httponly=True,
            secure=self.settings.effective_cookie_secure,
            samesite=self.settings.cookie_samesite,
            max_age=self.settings.session_ttl_seconds,
            path="/",
        )
        response.set_cookie(
            self.settings.csrf_cookie_name,
            csrf,
            httponly=False,
            secure=self.settings.effective_cookie_secure,
            samesite=self.settings.cookie_samesite,
            max_age=self.settings.session_ttl_seconds,
            path="/",
        )

    def clear_cookies(self, response: Response) -> None:
        response.delete_cookie(self.settings.session_cookie_name, path="/")
        response.delete_cookie(self.settings.csrf_cookie_name, path="/")

    def _create_session(
        self, user: User, ip: str | None, user_agent: str | None
    ) -> tuple[str, UserSession]:
        raw = secrets.token_urlsafe(32)
        bypass_mfa = (
            self.settings.allow_dev_mfa_bypass
            and not self.settings.require_mfa_privileged
        ) or user.role not in PrivilegedRoles.MFA_REQUIRED
        session = UserSession(
            user_id=user.id,
            token_hash=hash_token(raw),
            csrf_token=secrets.token_urlsafe(24),
            expires_at=utcnow() + timedelta(seconds=self.settings.session_ttl_seconds),
            ip_hash=hash_optional(ip),
            user_agent_hash=hash_optional(user_agent),
            mfa_completed=bypass_mfa
            or (not user.mfa_enabled and self.settings.allow_dev_mfa_bypass),
        )
        self.db.add(session)
        self.db.flush()
        return raw, session

    def _issue_email_token(self, user_id: str, purpose: str) -> str:
        raw = secrets.token_urlsafe(32)
        self.db.add(
            EmailToken(
                user_id=user_id,
                purpose=purpose,
                token_hash=hash_token(raw),
                expires_at=utcnow() + timedelta(hours=24),
            )
        )
        return raw

    def _consume_token(self, token: str, purpose: str) -> EmailToken:
        record = self.db.scalar(
            select(EmailToken).where(
                EmailToken.token_hash == hash_token(token),
                EmailToken.purpose == purpose,
            )
        )
        if (
            not record
            or record.consumed_at
            or (ensure_aware(record.expires_at) or utcnow()) < utcnow()
        ):
            raise AppError("TOKEN_INVALID", "This link is invalid or has expired.", 400)
        record.consumed_at = utcnow()
        return record


def grant_welcome_credits(db: Session, user: User, settings: Settings) -> None:
    grant_promotional(
        db,
        user.id,
        settings.promotional_grant_credits,
        key=f"welcome:{user.id}",
    )
