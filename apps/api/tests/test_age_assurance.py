import hashlib
import hmac
import json
from uuid import uuid4

import httpx

from app.config import get_settings
from app.models.enums import AgeVerificationStatus, UserStatus
from app.models.user import AgeVerification, User
from tests.conftest import become_active, csrf_for, register_verify_login


def test_sandbox_complete_still_works_in_test(client):
    register_verify_login(client)
    become_active(client)
    status = client.get("/v1/age-verification/status")
    assert status.json()["status"] == "PASSED"
    assert status.json()["account_status"] == "ACTIVE"


def test_sandbox_disabled_in_production(client, monkeypatch):
    register_verify_login(client)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ALLOW_SANDBOX_AGE_VERIFY", "true")
    monkeypatch.setenv("AGE_VERIFICATION_PROVIDER", "sandbox")
    get_settings.cache_clear()
    res = client.post(
        "/v1/age-verification/sandbox-complete",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"outcome": "PASSED"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "SANDBOX_DISABLED"
    get_settings.cache_clear()


def test_http_session_and_webhook_passed(client, monkeypatch):
    monkeypatch.setenv("AGE_VERIFICATION_PROVIDER", "http")
    monkeypatch.setenv("AGE_VERIFICATION_API_URL", "https://age.test")
    monkeypatch.setenv("AGE_VERIFICATION_API_KEY", "ak_test")
    monkeypatch.setenv("AGE_VERIFICATION_WEBHOOK_SECRET", "age-secret")
    monkeypatch.setenv("ALLOW_SANDBOX_AGE_VERIFY", "false")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/sessions")
        return httpx.Response(
            200,
            json={
                "session_id": "sess_abc",
                "handoff_url": "https://age.test/handoff/sess_abc",
            },
        )

    http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://age.test"
    )
    from app.age.providers import HttpAgeProvider

    original = HttpAgeProvider.__init__

    def patched(self, settings, client=None):
        original(self, settings, client=http)

    monkeypatch.setattr(HttpAgeProvider, "__init__", patched)

    login = register_verify_login(client)
    user_id = login["user"]["id"]
    sandbox = client.post(
        "/v1/age-verification/sandbox-complete",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"outcome": "PASSED"},
    )
    assert sandbox.status_code == 403
    started = client.post(
        "/v1/age-verification/session",
        headers={"X-CSRF-Token": csrf_for(client)},
    )
    assert started.status_code == 200, started.text
    assert started.json()["sandbox"] is False
    assert started.json()["handoff_url"] == "https://age.test/handoff/sess_abc"

    payload = {
        "session_id": "sess_abc",
        "user_id": user_id,
        "outcome": "PASSED",
        "assurance_level": "high",
        "date_of_birth": "1990-01-01",
        "document": "SHOULD_NEVER_BE_STORED",
    }
    raw = json.dumps(payload).encode()
    digest = hmac.new(b"age-secret", raw, hashlib.sha256).hexdigest()
    hooked = client.post(
        "/v1/webhooks/age-verification",
        content=raw,
        headers={"X-Signature": f"sha256={digest}"},
    )
    assert hooked.status_code == 200, hooked.text
    assert hooked.json()["status"] == "PASSED"
    again = client.post(
        "/v1/webhooks/age-verification",
        content=raw,
        headers={"X-Signature": f"sha256={digest}"},
    )
    assert again.status_code == 200

    from app.db import get_session_factory
    from sqlalchemy import select

    db = get_session_factory()()
    user = db.get(User, user_id)
    assert user.status == UserStatus.ACTIVE
    assert user.age_verification_status == AgeVerificationStatus.PASSED
    assert not hasattr(user, "date_of_birth")
    rows = db.scalars(
        select(AgeVerification).where(AgeVerification.user_id == user_id)
    ).all()
    assert all(row.raw_payload_retained is False for row in rows)
    assert all("1990" not in (row.assurance_level or "") for row in rows)
    db.close()

    gen = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "An original fictional adult character, clearly 29 years old",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert gen.status_code == 200, gen.text
    get_settings.cache_clear()


def test_webhook_failed_does_not_unlock(client, monkeypatch):
    monkeypatch.setenv("AGE_VERIFICATION_WEBHOOK_SECRET", "age-secret")
    get_settings.cache_clear()
    login = register_verify_login(client)
    user_id = login["user"]["id"]
    payload = json.dumps(
        {"user_id": user_id, "outcome": "FAILED", "session_id": "sess_fail"}
    ).encode()
    digest = hmac.new(b"age-secret", payload, hashlib.sha256).hexdigest()
    res = client.post(
        "/v1/webhooks/age-verification",
        content=payload,
        headers={"X-Signature": f"sha256={digest}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "FAILED"
    gen = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "An original fictional adult character, clearly 29 years old",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert gen.status_code == 403
    get_settings.cache_clear()


def test_webhook_invalid_signature(client):
    res = client.post(
        "/v1/webhooks/age-verification",
        content=b'{"outcome":"PASSED"}',
        headers={"X-Signature": "sha256=nope"},
    )
    assert res.status_code == 401


def test_no_dob_columns():
    from app.models.user import AgeVerification, User

    assert not hasattr(User, "date_of_birth")
    assert not hasattr(AgeVerification, "date_of_birth")
    assert not hasattr(AgeVerification, "document")
