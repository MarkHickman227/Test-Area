from tests.conftest import become_active, csrf_for, register_verify_login


def test_unverified_cannot_generate(client):
    register_verify_login(client)
    res = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": "k1-unverified",
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": "An original fictional adult character, clearly 25 years old, studio portrait",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "AGE_VERIFICATION_REQUIRED"


def test_unverified_cannot_checkout(client):
    register_verify_login(client)
    res = client.post(
        "/v1/billing/checkout-session",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={"product_id": "credits-40"},
    )
    assert res.status_code in {403, 503}


def test_self_declared_dob_not_used():
    from app.models.user import User

    assert not hasattr(User, "date_of_birth")
