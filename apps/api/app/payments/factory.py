from __future__ import annotations

from app.config import Settings
from app.errors import AppError
from app.payments.base import PaymentProvider, SandboxProvider
from app.payments.stripe_adapter import StripeProvider


def make_provider(settings: Settings, stripe_client=None) -> PaymentProvider:
    if not settings.payments_enabled:
        raise AppError(
            "PAYMENTS_NOT_ENABLED",
            "Paid credit purchase is not enabled.",
            503,
        )
    if settings.payment_provider == "sandbox":
        return SandboxProvider(settings)
    if settings.payment_provider == "stripe":
        return StripeProvider(settings, client=stripe_client)
    raise AppError(
        "PAYMENTS_NOT_CONFIGURED",
        "No payment provider is configured.",
        503,
    )
