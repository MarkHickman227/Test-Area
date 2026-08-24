from uuid import uuid4

from tests.conftest import become_active, csrf_for, register_verify_login


def test_delete_output_and_account(client):
    register_verify_login(client)
    become_active(client)
    created = client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "prompt": "An original fictional adult character, clearly 27 years old, charcoal drawing",
            "aspect_ratio": "3:2",
            "resolution": "1152x768",
            "image_count": 1,
        },
    )
    assert created.status_code == 200, created.text
    output_id = client.get("/v1/library/outputs").json()[0]["id"]
    deleted = client.delete(
        f"/v1/library/outputs/{output_id}", headers={"X-CSRF-Token": csrf_for(client)}
    )
    assert deleted.status_code == 200
    assert "deletion_request_id" in deleted.json()
    assert client.get("/v1/library/outputs").json() == []
    exported = client.post(
        "/v1/account/export", headers={"X-CSRF-Token": csrf_for(client)}
    )
    assert exported.status_code == 200
    gone = client.post("/v1/account/delete", headers={"X-CSRF-Token": csrf_for(client)})
    assert gone.status_code == 200
    me = client.get("/v1/account")
    assert me.status_code == 401
