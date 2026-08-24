from uuid import uuid4

from tests.conftest import become_active, csrf_for, register_verify_login


def test_users_cannot_see_each_others_jobs(client):
    register_verify_login(client, email="alpha@example.com")
    become_active(client)
    created = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "prompt": "An original fictional adult character, clearly 26 years old, oil painting",
            "aspect_ratio": "1:1",
            "resolution": "768x768",
            "image_count": 1,
        },
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["job_id"]
    outputs = client.get("/v1/library/outputs").json()
    output_id = outputs[0]["id"]
    client.post("/v1/auth/logout", headers={"X-CSRF-Token": csrf_for(client)})

    register_verify_login(client, email="beta@example.com")
    become_active(client)
    other_job = client.get(f"/v1/generations/{job_id}")
    assert other_job.status_code == 404
    other_output = client.get(f"/v1/library/outputs/{output_id}")
    assert other_output.status_code == 404
    listed = client.get("/v1/library/outputs").json()
    assert listed == []
