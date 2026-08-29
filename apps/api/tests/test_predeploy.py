import os
import sqlite3
import subprocess
from pathlib import Path
from uuid import uuid4

import pyotp

from app.config import get_settings
from app.db import reset_engine
from tests.conftest import become_active, csrf_for, register_verify_login

REPO_ROOT = Path(__file__).resolve().parents[3]


def _generate(client, prompt: str):
    return client.post(
        "/v1/generations",
        headers={"X-CSRF-Token": csrf_for(client)},
        json={
            "idempotency_key": uuid4().hex,
            "model_profile_id": "adult-illustration-v1",
            "style_preset_id": "cinematic-photo-v1",
            "prompt": prompt,
            "aspect_ratio": "2:3",
            "resolution": "768x1152",
            "image_count": 1,
        },
    )


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
    gen = _generate(
        client, "An original fictional adult character, clearly 31 years old"
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
    res = _generate(client, "a child in an adult scene")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PROMPT_BLOCKED"
    listed = client.get("/v1/generations").json()
    assert isinstance(listed, list)
    assert all(job["status"] not in {"QUEUED", "RUNNING", "COMPLETED"} for job in listed)


def test_release_age_then_generate_then_library(client):
    register_verify_login(client)
    become_active(client)
    res = _generate(
        client,
        "An original fictional adult character, clearly 32 years old, studio portrait",
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "COMPLETED"
    outputs = client.get("/v1/library/outputs")
    assert outputs.status_code == 200
    assert len(outputs.json()) == 1
    products = client.get("/v1/billing/products").json()
    assert all(item["available"] is False for item in products)


def test_release_support_search_hides_outputs(client):
    register_verify_login(client, email="visible-user@example.com")
    become_active(client)
    created = _generate(
        client,
        "An original fictional adult character, clearly 34 years old, ink drawing",
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
    row = found.json()[0]
    assert row["outputs_visible"] is False
    assert "outputs" not in row
    assert "url" not in row
    assert client.get("/v1/admin/queue").status_code == 403


def test_release_privileged_mfa_blocks_admin(client, monkeypatch):
    monkeypatch.setenv("REQUIRE_MFA_PRIVILEGED", "true")
    monkeypatch.setenv("ALLOW_DEV_MFA_BYPASS", "false")
    get_settings.cache_clear()
    try:
        login = client.post(
            "/v1/auth/login",
            json={"email": "admin@example.com", "password": "dev-admin-password"},
        )
        assert login.status_code == 200, login.text
        assert login.json()["mfa_required"] is True
        blocked = client.get("/v1/admin/queue")
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "MFA_REQUIRED"
        setup = client.post(
            "/v1/auth/mfa/setup", headers={"X-CSRF-Token": csrf_for(client)}
        )
        assert setup.status_code == 200, setup.text
        secret = setup.json()["secret"]
        bad = client.post(
            "/v1/auth/mfa/verify",
            headers={"X-CSRF-Token": csrf_for(client)},
            json={"code": "000000"},
        )
        assert bad.status_code == 401
        assert bad.json()["error"]["code"] == "MFA_INVALID"
        ok = client.post(
            "/v1/auth/mfa/verify",
            headers={"X-CSRF-Token": csrf_for(client)},
            json={"code": pyotp.TOTP(secret).now()},
        )
        assert ok.status_code == 200, ok.text
        queue = client.get("/v1/admin/queue")
        assert queue.status_code == 200, queue.text
    finally:
        get_settings.cache_clear()


def test_release_backup_restore_roundtrip(client, tmp_path):
    register_verify_login(client)
    become_active(client)
    created = _generate(
        client,
        "An original fictional adult character, clearly 33 years old, studio portrait",
    )
    assert created.status_code == 200, created.text
    settings = get_settings()
    db_url = settings.database_url
    storage = settings.storage_local_path
    reset_engine()
    db_path = db_url.removeprefix("sqlite+pysqlite:///")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
    finally:
        conn.close()
    backup_dir = tmp_path / "backups"
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["STORAGE_LOCAL_PATH"] = storage
    env["BACKUP_DIR"] = str(backup_dir)
    subprocess.check_call(
        [str(REPO_ROOT / "scripts" / "backup.sh")], cwd=REPO_ROOT, env=env
    )
    stamps = [p for p in backup_dir.iterdir() if p.is_dir()]
    assert len(stamps) == 1
    restored = tmp_path / "restored.db"
    subprocess.check_call(
        [str(REPO_ROOT / "scripts" / "restore.sh"), str(stamps[0]), str(restored)],
        cwd=REPO_ROOT,
        env=env,
    )
    conn = sqlite3.connect(restored)
    try:
        jobs = conn.execute("SELECT COUNT(*) FROM generation_jobs").fetchone()[0]
        outputs = conn.execute("SELECT COUNT(*) FROM generation_outputs").fetchone()[0]
    finally:
        conn.close()
    assert jobs >= 1
    assert outputs >= 1
