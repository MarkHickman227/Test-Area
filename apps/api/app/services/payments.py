from __future__ import annotations

import hashlib
import hmac
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import AppError
from app.models.billing import PaymentTransaction, Plan
from app.models.enums import AgeVerificationStatus, LedgerEventType, UserStatus
from app.models.user import User
from app.payments.factory import make_provider
from app.payments.stripe_adapter import verify_stripe_signature
from app.services.audit import write_audit
from app.services.credits import append_event, ledger_balance

CATALOG = [
    {
        "id": "credits-40",
        "name": "40 credits",
        "credits": 40,
        "amount_minor": 900,
        "currency": "GBP",
        "kind": "credits",
    },
    {
        "id": "credits-120",
        "name": "120 credits",
        "credits": 120,
        "amount_minor": 2400,
        "currency": "GBP",
        "kind": "credits",
    },
]

DISABLED_NOTE = "Payments disabled until a processor approves this service."
ENABLED_NOTE = (
    "Sandbox/test checkout only. Live card charging stays off until a processor "
    "confirms this business in writing."
)


def catalog(enabled: bool) -> list[dict]:
    note = ENABLED_NOTE if enabled else DISABLED_NOTE
    return [{**item, "available": enabled, "note": note} for item in CATALOG]


def product_by_id(product_id: str) -> dict:
    for item in CATALOG:
        if item["id"] == product_id:
            return item
    raise AppError("UNKNOWN_PRODUCT", "That product is not available.")


class PaymentService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def assert_can_pay(self, user: User) -> None:
        if (
            user.status != UserStatus.ACTIVE
            or user.age_verification_status != AgeVerificationStatus.PASSED
        ):
            raise AppError(
                "AGE_VERIFICATION_REQUIRED",
                "Complete age assurance before purchasing credits.",
                403,
            )

    def create_checkout(self, user: User, product_id: str) -> dict:
        self.assert_can_pay(user)
        product = product_by_id(product_id)
        provider = make_provider(self.settings)
        payment = PaymentTransaction(
            user_id=user.id,
            provider=provider.name,
            status="PENDING",
            amount_minor=int(product["amount_minor"]),
            currency=product["currency"],
            extra_metadata={
                "product_id": product["id"],
                "credits": product["credits"],
                "kind": "credits",
            },
        )
        self.db.add(payment)
        self.db.flush()
        result = provider.create_checkout(user, payment, product)
        if result.provider_ref:
            payment.provider_ref = result.provider_ref
        write_audit(
            self.db,
            action="billing.checkout_started",
            target_type="payment",
            target_id=payment.id,
            actor_user_id=user.id,
            metadata={"product_id": product_id, "provider": provider.name},
        )
        self.db.commit()
        return {
            "payment_id": payment.id,
            "provider": provider.name,
            "status": payment.status,
            "checkout_url": result.checkout_url,
            "sandbox": result.sandbox,
        }

    def complete_sandbox(self, user: User, payment_id: str) -> dict:
        if self.settings.payment_provider != "sandbox":
            raise AppError(
                "PAYMENTS_NOT_ENABLED",
                "Sandbox completion is only available with the sandbox provider.",
                503,
            )
        payment = self.db.get(PaymentTransaction, payment_id)
        if not payment or payment.user_id != user.id:
            raise AppError("PAYMENT_NOT_FOUND", "Payment was not found.", 404)
        self.fulfill(payment, source="sandbox")
        return {
            "payment_id": payment.id,
            "status": payment.status,
            "balance": ledger_balance(self.db, user.id),
        }

    def fulfill(self, payment: PaymentTransaction, source: str) -> None:
        if payment.status == "COMPLETED":
            return
        if payment.status not in {"PENDING", "PROCESSING"}:
            raise AppError("PAYMENT_NOT_FULFILLABLE", "Payment cannot be completed.")
        meta = payment.extra_metadata or {}
        credits = int(meta.get("credits") or 0)
        if credits <= 0:
            raise AppError("UNKNOWN_PRODUCT", "Payment has no credit grant.")
        append_event(
            self.db,
            user_id=payment.user_id,
            event_type=LedgerEventType.PURCHASED_CREDITS,
            amount=credits,
            idempotency_key=f"purchase:{payment.id}",
            reason_code="PURCHASE",
            related_payment_id=payment.id,
            metadata={"source": source, "product_id": meta.get("product_id")},
        )
        payment.status = "COMPLETED"
        write_audit(
            self.db,
            action="billing.purchase_completed",
            target_type="payment",
            target_id=payment.id,
            metadata={"credits": credits, "source": source},
        )
        self.db.commit()

    def subscribe(self, user: User, plan_id: str) -> dict:
        self.assert_can_pay(user)
        make_provider(self.settings)
        if self.settings.payment_provider != "sandbox":
            raise AppError(
                "PAYMENTS_NOT_ENABLED",
                "Paid plans stay disabled until a processor approves this service.",
                503,
            )
        if plan_id not in {"standard", "creator"}:
            raise AppError("UNKNOWN_PRODUCT", "That plan is not available.")
        plan = self.db.get(Plan, plan_id)
        if not plan or not plan.active:
            raise AppError("UNKNOWN_PRODUCT", "That plan is not available.")
        user.plan_id = plan.id
        write_audit(
            self.db,
            action="billing.plan_changed",
            target_type="user",
            target_id=user.id,
            actor_user_id=user.id,
            metadata={"plan_id": plan.id},
        )
        self.db.commit()
        return {"plan_id": user.plan_id}

    def handle_webhook(
        self, raw: bytes, *, stripe_signature: str | None, x_signature: str | None
    ) -> dict:
        if not self.settings.payments_enabled:
            raise AppError(
                "PAYMENTS_NOT_ENABLED",
                "Payment webhooks are disabled until a processor is approved.",
                503,
            )
        if self.settings.payment_provider == "stripe":
            verify_stripe_signature(
                self.settings.stripe_webhook_secret, raw, stripe_signature or ""
            )
            body = _parse_json(raw)
            return self._handle_stripe_event(body)
        if self.settings.payment_provider != "sandbox":
            raise AppError(
                "PAYMENTS_NOT_CONFIGURED",
                "No payment provider is configured.",
                503,
            )
        verify_hmac(self.settings.payment_webhook_secret, raw, x_signature)
        body = _parse_json(raw)
        payment_id = body.get("payment_id")
        payment = self.db.get(PaymentTransaction, payment_id) if payment_id else None
        if not payment:
            raise AppError("PAYMENT_NOT_FOUND", "Unknown payment for webhook.", 404)
        event = body.get("event") or body.get("type")
        if event in {"checkout.completed", "payment.completed"}:
            self.fulfill(payment, source="webhook")
        return {"ok": True, "status": payment.status}

    def _handle_stripe_event(self, body: dict) -> dict:
        event_type = body.get("type")
        obj = (body.get("data") or {}).get("object") or {}
        payment_id = (obj.get("metadata") or {}).get("payment_id")
        provider_ref = obj.get("id")
        payment = None
        if payment_id:
            payment = self.db.get(PaymentTransaction, payment_id)
        if payment is None and provider_ref:
            payment = self.db.scalar(
                select(PaymentTransaction).where(
                    PaymentTransaction.provider == "stripe",
                    PaymentTransaction.provider_ref == provider_ref,
                )
            )
        if not payment:
            raise AppError("PAYMENT_NOT_FOUND", "Unknown payment for webhook.", 404)
        if provider_ref and not payment.provider_ref:
            payment.provider_ref = str(provider_ref)
        if event_type == "checkout.session.completed":
            self.fulfill(payment, source="stripe_webhook")
        return {"ok": True, "status": payment.status}


def verify_hmac(secret: str, raw: bytes, header: str | None) -> None:
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    provided = (header or "").removeprefix("sha256=")
    if not provided or not hmac.compare_digest(expected, provided):
        raise AppError("WEBHOOK_INVALID", "Webhook signature was not valid.", 401)


def _parse_json(raw: bytes) -> dict:
    try:
        body = json.loads(raw.decode() if raw else "{}")
    except json.JSONDecodeError as exc:
        raise AppError(
            "WEBHOOK_INVALID", "Webhook payload was not valid JSON.", 400
        ) from exc
    if not isinstance(body, dict):
        raise AppError("WEBHOOK_INVALID", "Webhook payload was not valid JSON.", 400)
    return body
