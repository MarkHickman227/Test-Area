from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, require_auth
from app.models.billing import CreditLedger, Plan
from app.schemas.billing import (
    BalanceResponse,
    CheckoutRequest,
    CheckoutSessionResponse,
    LedgerItem,
    Product,
    RefundRequest,
    SandboxCompleteRequest,
    SubscribeRequest,
)
from app.services.audit import write_audit
from app.services.credits import ledger_balance
from app.services.payments import PaymentService, catalog

router = APIRouter(prefix="/v1/billing", tags=["billing"])


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


@router.get("/plans")
def plans(ctx: AuthContext = Depends(require_auth), db: Session = Depends(get_db)):
    settings = get_settings()
    rows = db.scalars(select(Plan).where(Plan.active.is_(True))).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "max_images_per_job": p.max_images_per_job,
            "allows_priority": p.allows_priority,
            "hourly_job_limit": p.hourly_job_limit,
            "monthly_credits": p.monthly_credits,
            "current": p.id == ctx.user.plan_id,
            "paid": p.id != "standard",
            "available": p.id == "standard" or settings.payments_enabled,
        }
        for p in rows
    ]


@router.post("/subscribe")
def subscribe(
    payload: SubscribeRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return PaymentService(db, get_settings()).subscribe(ctx.user, payload.product_id)


@router.get("/products", response_model=list[Product])
def products(_: AuthContext = Depends(require_auth)):
    return catalog(get_settings().payments_enabled)


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
def checkout(
    payload: CheckoutRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return PaymentService(db, get_settings()).create_checkout(
        ctx.user, payload.product_id
    )


@router.post("/sandbox-complete")
def sandbox_complete(
    payload: SandboxCompleteRequest,
    ctx: AuthContext = Depends(require_auth),
    db: Session = Depends(get_db),
):
    return PaymentService(db, get_settings()).complete_sandbox(
        ctx.user, payload.payment_id
    )


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
