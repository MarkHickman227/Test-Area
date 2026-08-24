import hashlib
import hmac
import json
from uuid import uuid4

import httpx

from app.config import get_settings
from tests.conftest import become_active, csrf_for, register_verify_login


def _enable_sandbox(monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("PAYMENT_PROVIDER", "sandbox")
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "test-pay-secret")
    get_settings.cache_clear()


def test_products_unavailable_when_disabled(client):
    register_verify_login(client)
    become_active(client)
    res = client.get("/v1/billing/products")
    assert res.status_code == 200
    assert all(item["available"] is False for item in res.json())
    checkout = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-40"},
    )
    assert checkout.status_code == 503
    assert checkout.json()["error"]["code"] == "PAYMENTS_NOT_ENABLED"


def test_sandbox_checkout_grants_credits_once(client, monkeypatch):
    _enable_sandbox(monkeypatch)
    register_verify_login(client)
    become_active(client)
    start = client.get("/v1/billing/balance").json()["balance"]
    products = client.get("/v1/billing/products").json()
    assert products[0]["available"] is True
    checkout = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-40"},
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body["sandbox"] is True
    assert body["provider"] == "sandbox"
    done = client.post(
        "/v1/billing/sandbox-complete",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"payment_id": body["payment_id"]},
    )
    assert done.status_code == 200, done.text
    assert done.json()["balance"] == start + 40
    again = client.post(
        "/v1/billing/sandbox-complete",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"payment_id": body["payment_id"]},
    )
    assert again.status_code == 200
    assert again.json()["balance"] == start + 40
    ledger = client.get("/v1/billing/ledger").json()
    purchases = [row for row in ledger if row["event_type"] == "PURCHASED_CREDITS"]
    assert len(purchases) == 1
    assert purchases[0]["amount"] == 40
    get_settings.cache_clear()


def test_sandbox_webhook_hmac(client, monkeypatch):
    _enable_sandbox(monkeypatch)
    register_verify_login(client)
    become_active(client)
    start = client.get("/v1/billing/balance").json()["balance"]
    checkout = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-120"},
    )
    payment_id = checkout.json()["payment_id"]
    payload = json.dumps(
        {"event": "checkout.completed", "payment_id": payment_id}
    ).encode()
    bad = client.post(
        "/v1/webhooks/payments", content=payload, headers={"X-Signature": "nope"}
    )
    assert bad.status_code == 401
    digest = hmac.new(b"test-pay-secret", payload, hashlib.sha256).hexdigest()
    ok = client.post(
        "/v1/webhooks/payments",
        content=payload,
        headers={"X-Signature": f"sha256={digest}"},
    )
    assert ok.status_code == 200, ok.text
    assert client.get("/v1/billing/balance").json()["balance"] == start + 120
    get_settings.cache_clear()


def test_unverified_cannot_checkout_when_enabled(client, monkeypatch):
    _enable_sandbox(monkeypatch)
    register_verify_login(client)
    res = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-40"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "AGE_VERIFICATION_REQUIRED"
    get_settings.cache_clear()


def test_sandbox_subscribe_creator(client, monkeypatch):
    _enable_sandbox(monkeypatch)
    register_verify_login(client)
    become_active(client)
    res = client.post(
        "/v1/billing/subscribe",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "creator"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["plan_id"] == "creator"
    get_settings.cache_clear()


def test_stripe_checkout_and_webhook(client, monkeypatch):
    monkeypatch.setenv("PAYMENTS_ENABLED", "true")
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/checkout/sessions"
        return httpx.Response(
            200,
            json={
                "id": "cs_test_123",
                "url": "https://checkout.stripe.test/cs_test_123",
            },
        )

    http = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.stripe.com",
    )

    from app.payments.stripe_adapter import StripeProvider

    original = StripeProvider.__init__

    def patched(self, settings, client=None):
        original(self, settings, client=http)

    monkeypatch.setattr(StripeProvider, "__init__", patched)

    register_verify_login(client)
    become_active(client)
    start = client.get("/v1/billing/balance").json()["balance"]
    checkout = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-40"},
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["provider"] == "stripe"
    assert "checkout.stripe.test" in checkout.json()["checkout_url"]
    payment_id = checkout.json()["payment_id"]
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "metadata": {"payment_id": payment_id, "user_id": "x"},
            }
        },
    }
    raw = json.dumps(event).encode()
    digest = hmac.new(b"whsec_test", b"1111." + raw, hashlib.sha256).hexdigest()
    hooked = client.post(
        "/v1/webhooks/payments",
        content=raw,
        headers={"Stripe-Signature": f"t=1111,v1={digest}"},
    )
    assert hooked.status_code == 200, hooked.text
    assert client.get("/v1/billing/balance").json()["balance"] == start + 40
    get_settings.cache_clear()


def test_webhook_disabled_without_flag(client):
    res = client.post(
        "/v1/webhooks/payments",
        content=b'{"event":"checkout.completed","payment_id":"'
        + uuid4().hex.encode()
        + b'"}',
        headers={"X-Signature": "sha256=abc"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "PAYMENTS_NOT_ENABLED"
