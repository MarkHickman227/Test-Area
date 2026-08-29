from uuid import uuid4

from tests.conftest import become_active, csrf_for, register_verify_login


def test_release_ready_and_safe_flags(client):
    ready = client.get("/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    health = client.get("/health")
    assert health.status_code == 200
    meta = client.get("/v1/meta/launch").json()
    assert meta["payments_enabled"] is False
    assert meta["payment_provider"] == "none"
    assert meta["generation_backend"] == "mock"
    assert meta["sandbox_age"] is True


def test_release_unverified_cannot_generate_or_checkout(client):
    register_verify_login(client)
    gen = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "An original fictional adult character, clearly 31 years old",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert gen.status_code == 403
    assert gen.json()["error"]["code"] == "AGE_VERIFICATION_REQUIRED"
    pay = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-40"},
    )
    assert pay.status_code in {403, 503}


def test_release_blocked_prompt_never_queues(client):
    register_verify_login(client)
    become_active(client)
    res = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "a child in an adult scene",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PROMPT_BLOCKED"
    listed = client.get("/v1/generations").json()
    assert isinstance(listed, list)
    assert all(job["status"] not in {"QUEUED", "RUNNING", "COMPLETED"} for job in listed)


def test_release_age_then_generate_then_library(client):
    register_verify_login(client)
    become_active(client)
    res = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "An original fictional adult character, clearly 32 years old, studio portrait",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "COMPLETED"
    outputs = client.get("/v1/library/outputs")
    assert outputs.status_code == 200
    assert len(outputs.json()) == 1
    products = client.get("/v1/billing/products").json()
    assert all(item["available"] is False for item in products)
