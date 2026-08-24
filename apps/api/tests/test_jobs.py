from uuid import uuid4

from tests.conftest import become_active, csrf_for, register_verify_login


def _create(client, prompt, key=None, count=1):
    return client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": key or uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": prompt,
            "negative_prompt": "celebrity, public figure, watermark",
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": count,
        },
    )


def test_prompt_blocked_never_queues(client):
    register_verify_login(client)
    become_active(client)
    res = _create(client, "a child in an adult scene")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PROMPT_BLOCKED"
    listed = client.get("/v1/generations")
    assert listed.status_code == 200
    assert all(job["status"] != "QUEUED" for job in listed.json())
    assert all(job["status"] != "RUNNING" for job in listed.json())


def test_successful_inline_job_and_library(client):
    register_verify_login(client)
    become_active(client)
    res = _create(
        client,
        "An original fictional adult character, clearly 25 years old, studio portrait",
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "COMPLETED"
    assert body["estimated_credit_cost"] >= 1
    outputs = client.get("/v1/library/outputs")
    assert outputs.status_code == 200
    items = outputs.json()
    assert len(items) == 1
    detail = client.get(f"/v1/library/outputs/{items[0]['id']}")
    assert detail.status_code == 200
    assert "25 years old" in detail.json()["prompt"]
    dl = client.post(
        f"/v1/library/outputs/{items[0]['id']}/download-url",
        headers={"X-CSRF-Token": csrf_for(client)},
    )
    assert dl.status_code == 200
    file_res = client.get(
        dl.json()["url"].split("localhost:3000")[-1]
        if "localhost" in dl.json()["url"]
        else dl.json()["url"]
    )
    if file_res.status_code != 200:
        file_res = client.get("/v1/library/files/" + items[0]["id"])
    # Proxied download uses storage key path
    path = dl.json()["url"]
    if path.startswith("http"):
        path = "/" + "/".join(path.split("/")[3:])
    file_res = client.get(path)
    assert file_res.status_code == 200
    assert file_res.headers["content-type"] == "image/png"


def test_cancel_only_while_queued(client):
    register_verify_login(client)
    become_active(client)
    res = _create(client, "An original fictional adult character, clearly 30 years old")
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert res.json()["status"] == "COMPLETED"
    cancel = client.post(
        f"/v1/generations/{job_id}/cancel", headers={"X-CSRF-Token": csrf_for(client)}
    )
    assert cancel.status_code == 400
    assert cancel.json()["error"]["code"] == "CANCEL_NOT_ALLOWED"


def test_idempotent_create(client):
    register_verify_login(client)
    become_active(client)
    key = "same-key-12345678"
    first = _create(
        client, "An original fictional adult character, clearly 28 years old", key=key
    )
    second = _create(
        client, "An original fictional adult character, clearly 28 years old", key=key
    )
    assert first.json()["job_id"] == second.json()["job_id"]
