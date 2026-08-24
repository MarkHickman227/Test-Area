from __future__ import annotations

from app.age.providers import AgeProvider, HttpAgeProvider, SandboxProvider
from app.config import Settings
from app.errors import AppError


def make_age_provider(settings: Settings, client=None) -> AgeProvider:
    if settings.age_verification_provider == "sandbox":
        return SandboxProvider(settings)
    if settings.age_verification_provider == "http":
        return HttpAgeProvider(settings, client=client)
    raise AppError(
        "AGE_PROVIDER_NOT_CONFIGURED",
        "No age-assurance provider is configured.",
        503,
    )
