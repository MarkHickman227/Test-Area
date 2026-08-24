from __future__ import annotations

from datetime import datetime

from app.schemas.common import APIModel


class Product(APIModel):
    id: str
    name: str
    credits: int
    available: bool
    note: str
    amount_minor: int = 0
    currency: str = "GBP"


class CheckoutRequest(APIModel):
    product_id: str


class CheckoutSessionResponse(APIModel):
    payment_id: str
    provider: str
    status: str
    checkout_url: str | None = None
    sandbox: bool = False


class SandboxCompleteRequest(APIModel):
    payment_id: str


class SubscribeRequest(APIModel):
    product_id: str


class BalanceResponse(APIModel):
    balance: int
    currency: str = "CREDIT"


class LedgerItem(APIModel):
    id: str
    event_type: str
    amount: int
    reason_code: str
    related_job_id: str | None
    created_at: datetime


class RefundRequest(APIModel):
    reason: str
    job_id: str | None = None
