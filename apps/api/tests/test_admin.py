from uuid import uuid4

from tests.conftest import become_active, csrf_for, register_verify_login


def test_moderator_reviews_held_job(client):
    register_verify_login(client, email="held@example.com")
    become_active(client)
    created = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "prompt": "young adult editorial photography, original fictional character",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "QUEUED"
    job_id = created.json()["job_id"]
    client.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf_for(client)})

    login = client.post(
        "/v1/auth/login",
        json={"email": "admin@example.com", "password": "dev-admin-password"},
    )
    assert login.status_code == 200, login.text
    queue = client.get("/v1/admin/queue")
    assert queue.status_code == 200
    held_ids = [row["id"] for row in queue.json()["held_jobs"]]
    assert job_id in held_ids
    decided = client.post(
        f"/v1/admin/jobs/{job_id}/decision",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "decision": "BLOCK",
            "reason_code": "AMBIGUOUS_AGE",
            "rationale": "Held prompt blocked in test.",
        },
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "BLOCKED"
