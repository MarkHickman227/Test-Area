from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, require_auth
from app.errors import AppError
from app.models.billing import CreditLedger
from app.models.enums import AgeVerificationStatus, UserStatus
from app.schemas.billing import (
    BalanceResponse,
    CheckoutRequest,
    LedgerItem,
    Product,
    RefundRequest,
)
from app.services.audit import write_audit
from app.services.credits import ledger_balance

router = APIRouter(prefix="/v1/billing", tags=["billing"])

PRODUCTS = [
    Product(
        id="credits-40",
        name="40 credits",
        credits=40,
        available=False,
        note="Payments disabled until a processor approves this service.",
    ),
    Product(
        id="credits-120",
        name="120 credits",
        credits=120,
        available=False,
        note="Payments disabled until a processor approves this service.",
    ),
]


@router.get("/balance", response_model=BalanceResponse)
def balance(ctx: AuthContext = Depends(require_auth), db: Session = Depends(get_db)):
    return BalanceResponse(balance=ledger_balance(db, ctx.user.id))


@router.get("/ledger", response_model=list[LedgerItem])
def ledger(ctx: AuthContext = Depends(require_auth), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(CreditLedger)
        .where(CreditLedger.user_id == ctx.user.id)
        .order_by(CreditLedger.created_at.desc())
        .limit(200)
    ).all()
    return [
        LedgerItem(
            id=row.id,
            event_type=row.event_type,
            amount=row.amount,
            reason_code=row.reason_code,
            related_job_id=row.related_job_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/products", response_model=list[Product])
def products(_: AuthContext = Depends(require_auth)):
    return PRODUCTS


@router.post("/checkout-session")
def checkout(payload: CheckoutRequest, ctx: AuthContext = Depends(require_auth)):
    settings = get_settings()
    if not settings.payments_enabled:
        raise AppError(
            "PAYMENTS_NOT_ENABLED", "Paid credit purchase is not enabled.", 503
        )
    if (
        ctx.user.status != UserStatus.ACTIVE
        or ctx.user.age_verification_status != AgeVerificationStatus.PASSED
    ):
        raise AppError(
            "AGE_VERIFICATION_REQUIRED",
            "Complete age assurance before purchasing credits.",
            403,
        )
    raise AppError("PAYMENTS_NOT_ENABLED", "Paid credit purchase is not enabled.", 503)


@router.post("/refund-request")
def refund_request(
    payload: RefundRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    write_audit(
        db,
        action="billing.refund_requested",
        target_type="user",
        target_id=ctx.user.id,
        actor_user_id=ctx.user.id,
        metadata={"reason": payload.reason, "job_id": payload.job_id},
    )
    db.commit()
    return {"ok": True, "status": "RECEIVED"}
