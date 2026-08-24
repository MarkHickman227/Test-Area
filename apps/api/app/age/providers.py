from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import httpx

from app.config import Settings
from app.errors import AppError
from app.models.user import User


@dataclass
class AgeSession:
    session_id: str
    handoff_url: str
    sandbox: bool


class AgeProvider:
    name = "none"

    def create_session(self, user: User) -> AgeSession:
        raise AppError(
            "AGE_PROVIDER_NOT_CONFIGURED",
            "No age-assurance provider is configured.",
            503,
        )


class SandboxProvider(AgeProvider):
    name = "sandbox"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_session(self, user: User) -> AgeSession:
        if not self.settings.sandbox_age_allowed:
            raise AppError(
                "SANDBOX_DISABLED",
                "Sandbox age assurance is disabled.",
                403,
            )
        return AgeSession(
            session_id=f"sandbox:{user.id}:{uuid4().hex[:12]}",
            handoff_url=f"{self.settings.app_base_url}/age-verification?sandbox=1",
            sandbox=True,
        )


class HttpAgeProvider(AgeProvider):
    """Generic HTTPS age-assurance vendor. Keys are not a compliance sign-off."""

    name = "http"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if (
            not settings.age_verification_api_url
            or not settings.age_verification_api_key
        ):
            raise AppError(
                "AGE_PROVIDER_NOT_CONFIGURED",
                "Age-assurance API URL and key are required for the HTTP provider.",
                503,
            )
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=settings.age_verification_api_url.rstrip("/"),
            timeout=20,
        )

    def create_session(self, user: User) -> AgeSession:
        payload = {
            "user_id": user.id,
            "return_url": f"{self.settings.app_base_url}/age-verification",
            "webhook_url": (
                f"{self.settings.api_base_url}/v1/webhooks/age-verification"
            ),
        }
        try:
            response = self._client.post(
                "/v1/sessions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.settings.age_verification_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AppError(
                "AGE_PROVIDER_ERROR",
                "The age-assurance provider could not start a session.",
                502,
            ) from exc
        data = response.json()
        session_id = data.get("session_id")
        handoff = data.get("handoff_url")
        if not session_id or not handoff:
            raise AppError(
                "AGE_PROVIDER_ERROR",
                "The age-assurance provider returned an incomplete session.",
                502,
            )
        return AgeSession(
            session_id=str(session_id),
            handoff_url=str(handoff),
            sandbox=False,
        )
