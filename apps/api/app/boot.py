from __future__ import annotations

from app.config import Settings

WEAK_SECRETS = {
    "",
    "dev-secret-change-me",
    "change-me-to-a-long-random-string",
    "dev-webhook-secret",
    "change-me-webhook",
    "dev-payment-webhook",
    "change-me-payment-webhook",
    "minioadmin",
    "replace-with-fernet-key",
    "change-me-minio",
    "dev-admin-password",
    "dev-user-password",
}


class BootError(RuntimeError):
    pass


def validate_settings(settings: Settings) -> list[str]:
    """Return problems that block staging/production boot. Dev/test are unrestricted."""
    if settings.is_dev:
        return []
    problems: list[str] = []
    if settings.secret_key in WEAK_SECRETS or len(settings.secret_key) < 32:
        problems.append("SECRET_KEY must be a unique value at least 32 characters.")
    if not settings.encryption_key or settings.encryption_key in WEAK_SECRETS:
        problems.append("ENCRYPTION_KEY must be a real Fernet key.")
    if settings.is_sqlite:
        problems.append("SQLite is not allowed outside development.")
    if settings.allow_dev_mfa_bypass:
        problems.append("ALLOW_DEV_MFA_BYPASS must be false.")
    if not settings.require_mfa_privileged:
        problems.append("REQUIRE_MFA_PRIVILEGED must be true.")
    if settings.age_verification_provider != "http":
        problems.append("AGE_VERIFICATION_PROVIDER must be http.")
    if not settings.age_verification_api_url or not settings.age_verification_api_key:
        problems.append("Age-assurance API URL and key are required.")
    if settings.age_verification_webhook_secret in WEAK_SECRETS:
        problems.append("AGE_VERIFICATION_WEBHOOK_SECRET must be rotated.")
    if settings.allow_sandbox_age_verify:
        problems.append("ALLOW_SANDBOX_AGE_VERIFY must be false.")
    if settings.generation_backend != "mock":
        problems.append(
            "GENERATION_BACKEND must stay mock until a licensed GPU host is attached."
        )
    if settings.payments_enabled:
        if not settings.payments_processor_attested:
            problems.append(
                "PAYMENTS_ENABLED requires PAYMENTS_PROCESSOR_ATTESTED after written approval."
            )
        if settings.payment_provider != "stripe" or not settings.stripe_secret_key:
            problems.append("Live payments require PAYMENT_PROVIDER=stripe and keys.")
        if settings.stripe_secret_key in WEAK_SECRETS:
            problems.append("STRIPE_SECRET_KEY is not valid.")
    if (
        settings.storage_backend == "minio"
        and settings.minio_secret_key in WEAK_SECRETS
    ):
        problems.append("MINIO_SECRET_KEY must not be the example value.")
    return problems


def assert_runtime_safe(settings: Settings) -> None:
    problems = validate_settings(settings)
    if problems:
        raise BootError(
            "Unsafe staging/production configuration: " + " ".join(problems)
        )
