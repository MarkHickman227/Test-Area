from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.config import get_settings
from app.deps import AuthContext, get_auth_service, require_auth
from app.models.enums import PrivilegedRoles
from app.schemas.auth import (
    LoginRequest,
    MfaVerifyRequest,
    PasswordForgotRequest,
    PasswordResetRequest,
    RegisterRequest,
    SessionResponse,
    UserPublic,
    VerifyEmailRequest,
)
from app.services.access import (
    assert_country_allowed,
    check_rate_limit,
    request_country,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _user_public(user) -> UserPublic:
    return UserPublic.model_validate(user)


@router.post("/register", status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
):
    settings = get_settings()
    check_rate_limit(
        f"register:{request.client.host if request.client else 'unknown'}",
        settings.auth_rate_limit_per_minute,
    )
    country = request_country(request)
    assert_country_allowed(settings, country)
    user = auth.register(
        payload.email,
        payload.password,
        payload.acceptances.model_dump(),
        ip=request.client.host if request.client else None,
        request_id=getattr(request.state, "request_id", None),
        invite_code=payload.invite_code,
        country_code=country,
    )
    return {"user": _user_public(user)}


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    auth: AuthService = Depends(get_auth_service),
):
    settings = get_settings()
    check_rate_limit(
        f"login:{request.client.host if request.client else 'unknown'}",
        settings.auth_rate_limit_per_minute,
    )
    assert_country_allowed(settings, request_country(request))
    user, session, raw = auth.login(
        payload.email,
        payload.password,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    auth.attach_session_cookies(response, raw, session.csrf_token)
    mfa_required = (
        user.role in PrivilegedRoles.MFA_REQUIRED
        and settings.require_mfa_privileged
        and not session.mfa_completed
    )
    return SessionResponse(
        user=_user_public(user),
        csrf_token=session.csrf_token,
        mfa_required=mfa_required,
    )


@router.post("/logout")
def logout(
    response: Response,
    ctx: AuthContext = Depends(require_auth),
    auth: AuthService = Depends(get_auth_service),
):
    auth.logout(ctx.session)
    auth.clear_cookies(response)
    return {"ok": True}


@router.post("/verify-email")
def verify_email(
    payload: VerifyEmailRequest, auth: AuthService = Depends(get_auth_service)
):
    user = auth.verify_email(payload.token)
    return {"user": _user_public(user)}


@router.post("/password/forgot")
def password_forgot(
    payload: PasswordForgotRequest, auth: AuthService = Depends(get_auth_service)
):
    auth.request_password_reset(payload.email)
    return {"ok": True}


@router.post("/password/reset")
def password_reset(
    payload: PasswordResetRequest, auth: AuthService = Depends(get_auth_service)
):
    auth.reset_password(payload.token, payload.password)
    return {"ok": True}


@router.post("/mfa/setup")
def mfa_setup(
    ctx: AuthContext = Depends(require_auth),
    auth: AuthService = Depends(get_auth_service),
):
    secret, uri = auth.setup_mfa(ctx.user)
    return {"otpauth_url": uri, "secret": secret}


@router.post("/mfa/verify")
def mfa_verify(
    payload: MfaVerifyRequest,
    ctx: AuthContext = Depends(require_auth),
    auth: AuthService = Depends(get_auth_service),
):
    auth.verify_mfa(ctx.user, ctx.session, payload.code)
    return {"ok": True}


@router.post("/refresh")
def refresh(ctx: AuthContext = Depends(require_auth)):
    return SessionResponse(
        user=_user_public(ctx.user), csrf_token=ctx.session.csrf_token
    )
