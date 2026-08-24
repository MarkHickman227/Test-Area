from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Callable

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.crypto import CryptoService, get_crypto
from app.db import get_db
from app.errors import AppError
from app.models.enums import PrivilegedRoles, UserRole
from app.models.user import Session as UserSession, User
from app.services.age import AgeVerificationService
from app.services.auth import AuthService
from app.services.jobs import JobService
from app.services.mail import MailService, hash_token
from app.services.storage import LocalStorage, MinioStorage, StorageBackend
from sqlalchemy import select

_mail: MailService | None = None
_storage: StorageBackend | None = None


def get_mail() -> MailService:
    global _mail
    if _mail is None:
        _mail = MailService(get_settings())
    return _mail


def reset_singletons() -> None:
    global _mail, _storage
    _mail = None
    _storage = None
    from app.services.access import reset_rate_limits

    reset_rate_limits()


def get_storage(settings: Settings = Depends(get_settings)) -> StorageBackend:
    global _storage
    if _storage is None:
        if settings.storage_backend == "minio":
            _storage = MinioStorage(settings)
        else:
            _storage = LocalStorage(settings.storage_local_path, settings.app_base_url)
    return _storage


def get_auth_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    mail: MailService = Depends(get_mail),
    crypto: CryptoService = Depends(get_crypto),
) -> AuthService:
    return AuthService(db, settings, mail, crypto)


def get_job_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    crypto: CryptoService = Depends(get_crypto),
) -> JobService:
    return JobService(db, settings, crypto)


def get_age_service(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    crypto: CryptoService = Depends(get_crypto),
) -> AgeVerificationService:
    return AgeVerificationService(db, settings, crypto)


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class AuthContext:
    user: User
    session: UserSession


def _load_session(
    request: Request, db: Session, settings: Settings
) -> AuthContext | None:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        return None
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == hash_token(raw))
    )
    if not session or not session.is_active:
        return None
    user = db.get(User, session.user_id)
    if not user:
        return None
    return AuthContext(user=user, session=session)


def require_auth(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> AuthContext:
    ctx = _load_session(request, db, settings)
    if not ctx:
        raise AppError("UNAUTHENTICATED", "Sign in required.", 401)
    if request.method not in SAFE_METHODS:
        header = x_csrf_token or request.headers.get("x-csrf-token")
        if not header or header != ctx.session.csrf_token:
            raise AppError("CSRF_FAILED", "Missing or invalid CSRF token.", 403)
    request.state.user_id = ctx.user.id
    return ctx


def optional_auth(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthContext | None:
    return _load_session(request, db, settings)


def require_roles(*roles: UserRole) -> Callable:
    def dependency(ctx: AuthContext = Depends(require_auth)) -> AuthContext:
        if (
            ctx.user.role not in {r.value for r in roles}
            and ctx.user.role != UserRole.SUPER_ADMIN
        ):
            raise AppError("FORBIDDEN", "You do not have permission to do that.", 403)
        if ctx.user.role in PrivilegedRoles.MFA_REQUIRED:
            settings = get_settings()
            if settings.require_mfa_privileged and not ctx.session.mfa_completed:
                raise AppError(
                    "MFA_REQUIRED", "Complete multi-factor authentication.", 403
                )
        return ctx

    return dependency
