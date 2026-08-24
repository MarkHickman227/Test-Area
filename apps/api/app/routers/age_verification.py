from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from app.deps import AuthContext, get_age_service, require_auth
from app.schemas.account import AgeSandboxRequest
from app.services.age import AgeVerificationService

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
    age: AgeVerificationService = Depends(get_age_service),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw = await request.body()
    return age.handle_webhook(raw, x_signature)
