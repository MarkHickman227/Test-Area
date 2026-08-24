from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.errors import AppError
from app.models.billing import PaymentTransaction
from app.models.user import User


@dataclass
class CheckoutResult:
    checkout_url: str | None
    provider_ref: str | None = None
    sandbox: bool = False


class PaymentProvider:
    name = "none"

    def create_checkout(
        self, user: User, payment: PaymentTransaction, product: dict
    ) -> CheckoutResult:
        raise AppError(
            "PAYMENTS_NOT_CONFIGURED",
            "No payment provider is configured.",
            503,
        )


class SandboxProvider(PaymentProvider):
    name = "sandbox"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_checkout(
        self, user: User, payment: PaymentTransaction, product: dict
    ) -> CheckoutResult:
        url = f"{self.settings.app_base_url}/account?pay={payment.id}"
        return CheckoutResult(checkout_url=url, provider_ref=payment.id, sandbox=True)
