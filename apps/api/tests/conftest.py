from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("JOB_EXECUTION", "inline")
os.environ.setdefault("REQUIRE_MFA_PRIVILEGED", "false")
os.environ.setdefault("ALLOW_DEV_MFA_BYPASS", "true")
os.environ.setdefault("ALLOW_SANDBOX_AGE_VERIFY", "true")
os.environ.setdefault("MAIL_BACKEND", "console")
os.environ.setdefault("PAYMENTS_ENABLED", "false")
os.environ.setdefault("PAYMENT_PROVIDER", "none")
os.environ.setdefault("SECRET_KEY", "test-secret")

CONSENTS = {
    "terms": "tos-2026-08-01",
    "privacy": "privacy-2026-08-01",
    "content_policy": "content-2026-08-01",
    "age_policy": "age-2026-08-01",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("APP_ENV", "test")
    from app.config import get_settings
    from app.crypto import reset_crypto
    from app.db import reset_engine
    from app.deps import reset_singletons

    get_settings.cache_clear()
    reset_engine()
    reset_crypto()
    reset_singletons()
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
    reset_engine()
    reset_crypto()
    reset_singletons()


def csrf_for(client: TestClient) -> str:
    return client.cookies.get("pc_csrf") or ""


def register_verify_login(
    client: TestClient,
    email: str | None = None,
    password: str = "correct-horse-battery",
) -> dict:
    email = email or f"user-{uuid4().hex[:8]}@example.com"
    res = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "acceptances": CONSENTS},
    )
    assert res.status_code == 201, res.text
    from app.deps import get_mail

    mail = get_mail()
    token = mail.outbox[-1]["body"].split("token=")[-1].strip()
    assert (
        client.post("/v1/auth/verify-email", json={"token": token}).status_code == 200
    )
    login = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()


def become_active(client: TestClient) -> None:
    res = client.post(
        "/v1/age-verification/sandbox-complete",
        json={"outcome": "PASSED"},
        headers={"X-CSRF-Token": csrf_for(client)},
    )
    assert res.status_code == 200, res.text
