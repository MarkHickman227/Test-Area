from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services.payments import PaymentService

router = APIRouter(tags=["billing"])


@router.post("/v1/webhooks/payments")
async def payments_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    x_signature: str | None = Header(default=None, alias="X-Signature"),
):
    raw = await request.body()
    return PaymentService(db, get_settings()).handle_webhook(
        raw, stripe_signature=stripe_signature, x_signature=x_signature
    )
