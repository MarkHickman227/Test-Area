from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.errors import AppError
from app.models.billing import PaymentTransaction
from app.models.user import User
from app.payments.base import CheckoutResult, PaymentProvider


class StripeProvider(PaymentProvider):
    """Checkout Sessions over HTTPS. Presence of keys is not processor approval."""

    name = "stripe"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.stripe_secret_key:
            raise AppError(
                "PAYMENTS_NOT_CONFIGURED",
                "Stripe keys are not configured.",
                503,
            )
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=settings.stripe_api_base.rstrip("/"),
            timeout=20,
        )

    def create_checkout(
        self, user: User, payment: PaymentTransaction, product: dict
    ) -> CheckoutResult:
        success = f"{self.settings.app_base_url}/account?pay=success"
        cancel = f"{self.settings.app_base_url}/account?pay=cancel"
        form = {
            "mode": "payment",
            "success_url": success,
            "cancel_url": cancel,
            "client_reference_id": user.id,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": product["currency"].lower(),
            "line_items[0][price_data][unit_amount]": str(product["amount_minor"]),
            "line_items[0][price_data][product_data][name]": product["name"],
            "metadata[payment_id]": payment.id,
            "metadata[user_id]": user.id,
            "metadata[product_id]": product["id"],
        }
        try:
            response = self._client.post(
                "/v1/checkout/sessions",
                content=urlencode(form),
                headers={
                    "Authorization": f"Bearer {self.settings.stripe_secret_key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "PAYMENTS_PROVIDER_ERROR",
                "The payment provider could not start checkout.",
                502,
            ) from exc
        data = response.json()
        session_id = data.get("id")
        url = data.get("url")
        if not session_id or not url:
            raise AppError(
                "PAYMENTS_PROVIDER_ERROR",
                "The payment provider returned an incomplete session.",
                502,
            )
        return CheckoutResult(checkout_url=str(url), provider_ref=str(session_id))


def verify_stripe_signature(secret: str, payload: bytes, header: str) -> None:
    parts: dict[str, str] = {}
    for item in (header or "").split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip()] = value.strip()
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature or not secret:
        raise AppError("WEBHOOK_INVALID", "Webhook signature was not valid.", 401)
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + payload,
        hashlib.sha256,
    ).hexdigest()
    try:
        valid = hmac.compare_digest(expected, signature)
    except ValueError:
        valid = False
    if not valid:
        raise AppError("WEBHOOK_INVALID", "Webhook signature was not valid.", 401)
