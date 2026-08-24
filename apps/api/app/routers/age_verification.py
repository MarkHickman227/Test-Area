from __future__ import annotations

import hmac
import json

from fastapi import APIRouter, Depends, Header, Request

from app.config import get_settings
from app.deps import AuthContext, get_age_service, require_auth
from app.errors import AppError
from app.models.user import User
from app.schemas.account import AgeSandboxRequest
from app.services.age import AgeVerificationService
from sqlalchemy.orm import Session
from app.db import get_db

router = APIRouter(tags=["age-verification"])


@router.post("/v1/age-verification/session")
def create_session(
    ctx: AuthContext = Depends(require_auth),
    age: AgeVerificationService = Depends(get_age_service),
):
    return age.create_session(ctx.user)


@router.get("/v1/age-verification/status")
def status(ctx: AuthContext = Depends(require_auth)):
    return {
        "status": ctx.user.age_verification_status,
        "age_verified_at": ctx.user.age_verified_at,
        "account_status": ctx.user.status,
    }


@router.post("/v1/age-verification/sandbox-complete")
def sandbox_complete(
    payload: AgeSandboxRequest,
    ctx: AuthContext = Depends(require_auth),
    age: AgeVerificationService = Depends(get_age_service),
):
    user = age.sandbox_complete(ctx.user, payload.outcome)
    return {"status": user.age_verification_status, "account_status": user.status}


@router.post("/v1/webhooks/age-verification")
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
    age: AgeVerificationService = Depends(get_age_service),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    settings = get_settings()
    raw = await request.body()
    expected = hmac.new(
        settings.age_verification_webhook_secret.encode(),
        raw,
        "sha256",
    ).hexdigest()
    provided = (x_signature or "").removeprefix("sha256=")
    if not provided or not hmac.compare_digest(expected, provided):
        raise AppError("WEBHOOK_INVALID", "Webhook signature was not valid.", 401)
    try:
        body = json.loads(raw.decode()) if raw else {}
    except json.JSONDecodeError:
        raise AppError("WEBHOOK_INVALID", "Webhook payload was not valid JSON.", 400)
    user_id = body.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise AppError(
            "USER_NOT_FOUND", "Unknown user for age-verification webhook.", 404
        )
    age.apply_outcome(
        user,
        body.get("outcome", "FAILED"),
        provider_ref=str(body.get("provider_ref", "webhook")),
        assurance_level=str(body.get("assurance_level", "high")),
    )
    return {"ok": True}
