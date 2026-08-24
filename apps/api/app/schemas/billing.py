from __future__ import annotations

from datetime import datetime

from app.schemas.common import APIModel


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


class Product(APIModel):
    id: str
    name: str
    credits: int
    available: bool
    note: str


class CheckoutRequest(APIModel):
    product_id: str


class RefundRequest(APIModel):
    reason: str
    job_id: str | None = None
