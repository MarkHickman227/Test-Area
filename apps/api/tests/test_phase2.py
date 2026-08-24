from uuid import uuid4

from tests.conftest import CONSENTS, become_active, csrf_for, register_verify_login


def test_waitlist_and_launch_meta(client):
    meta = client.get("/v1/meta/launch")
    assert meta.status_code == 200
    assert meta.json()["payments_enabled"] is False
    assert meta.json()["payment_provider"] == "none"
    assert meta.json()["generation_backend"] == "mock"
    assert meta.json()["age_provider"] == "sandbox"
    assert meta.json()["sandbox_age"] is True
    joined = client.post("/v1/waitlist", json={"email": "wait@example.com"})
    assert joined.status_code == 200
    again = client.post("/v1/waitlist", json={"email": "wait@example.com"})
    assert again.json()["already"] is True


def test_invite_required(client, monkeypatch):
    monkeypatch.setenv("INVITE_ONLY", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    blocked = client.post(
        "/v1/auth/register",
        json={
            "email": "need-invite@example.com",
            "password": "correct-horse-battery",
            "acceptances": CONSENTS,
        },
    )
    assert blocked.status_code == 400
    assert blocked.json()["error"]["code"] == "INVITE_REQUIRED"
    ok = client.post(
        "/v1/auth/register",
        json={
            "email": "has-invite@example.com",
            "password": "correct-horse-battery",
            "acceptances": CONSENTS,
            "invite_code": "WELCOME-DEV",
        },
    )
    assert ok.status_code == 201, ok.text
    get_settings.cache_clear()


def test_region_block(client, monkeypatch):
    monkeypatch.setenv("BLOCKED_COUNTRIES", "XX")
    from app.config import get_settings

    get_settings.cache_clear()
    res = client.post(
        "/v1/auth/register",
        headers={"X-Country-Code": "XX"},
        json={
            "email": "blocked-region@example.com",
            "password": "correct-horse-battery",
            "acceptances": CONSENTS,
        },
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "REGION_BLOCKED"
    get_settings.cache_clear()


def test_expanded_model_library(client):
    register_verify_login(client)
    options = client.get("/v1/generation/options")
    assert options.status_code == 200
    ids = {row["id"] for row in options.json()["model_profiles"]}
    assert "ink-illustration-v1" in ids
    assert "figurative-studio-v1" in ids


def test_support_cannot_see_outputs(client):
    register_verify_login(client, email="visible-user@example.com")
    become_active(client)
    created = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "prompt": "An original fictional adult character, clearly 34 years old, ink drawing",
            "aspect_ratio": "1:1",
            "resolution": "768x768",
            "image_count": 1,
        },
    )
    assert created.status_code == 200, created.text
    client.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf_for(client)})
    login = client.post(
        "/v1/auth/login",
        json={"email": "support@example.com", "password": "dev-support-password"},
    )
    assert login.status_code == 200, login.text
    found = client.get("/v1/admin/support/users?q=visible-user")
    assert found.status_code == 200, found.text
    assert found.json()[0]["outputs_visible"] is False
    queue = client.get("/v1/admin/queue")
    assert queue.status_code == 403


def test_finance_summary_and_capacity(client):
    login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "dev-admin-password"},
    )
    assert login.status_code == 200
    cap = client.get("/v1/admin/capacity")
    assert cap.status_code == 200
    assert "queue_depth" in cap.json()
    fin = client.get("/v1/admin/finance/summary")
    assert fin.status_code == 200
    assert fin.json()["payments_enabled"] is False
    assert fin.json()["payment_provider"] == "none"


def test_support_ticket(client):
    res = client.post(
        "/v1/support/tickets",
        json={
            "email": "help@example.com",
            "subject": "Cannot verify age",
            "body": "Sandbox handoff unclear",
        },
    )
    assert res.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "dev-admin-password"},
    )
    assert login.status_code == 200
    tickets = client.get("/v1/admin/support/tickets")
    assert tickets.status_code == 200
    assert any(row["subject"] == "Cannot verify age" for row in tickets.json())
