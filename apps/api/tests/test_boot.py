from app.boot import BootError, assert_runtime_safe, validate_settings
from app.config import get_settings


def _staging_env(monkeypatch, **overrides):
    values = {
        "APP_ENV": "staging",
        "SECRET_KEY": "staging-secret-key-value-32chars!",
        "ENCRYPTION_KEY": "staging-fernet-key-not-example",
        "DATABASE_URL": "postgresql+psycopg://privatecanvas:secret@postgres:5432/privatecanvas",
        "ALLOW_DEV_MFA_BYPASS": "false",
        "REQUIRE_MFA_PRIVILEGED": "true",
        "AGE_VERIFICATION_PROVIDER": "http",
        "AGE_VERIFICATION_API_URL": "https://age.example.test",
        "AGE_VERIFICATION_API_KEY": "ak_staging_example",
        "AGE_VERIFICATION_WEBHOOK_SECRET": "rotated-age-webhook-secret",
        "ALLOW_SANDBOX_AGE_VERIFY": "false",
        "GENERATION_BACKEND": "mock",
        "PAYMENTS_ENABLED": "false",
        "PAYMENTS_PROCESSOR_ATTESTED": "false",
        "STORAGE_BACKEND": "minio",
        "MINIO_SECRET_KEY": "rotated-minio-secret",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_dev_defaults_are_allowed(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    assert validate_settings(get_settings()) == []
    get_settings.cache_clear()


def test_staging_happy_path(monkeypatch):
    _staging_env(monkeypatch)
    try:
        assert validate_settings(get_settings()) == []
        assert_runtime_safe(get_settings())
        assert get_settings().effective_cookie_secure is True
    finally:
        get_settings.cache_clear()


def test_staging_rejects_sqlite_and_sandbox(monkeypatch):
    _staging_env(
        monkeypatch,
        DATABASE_URL="sqlite+pysqlite:///./data/privatecanvas.db",
        AGE_VERIFICATION_PROVIDER="sandbox",
        ALLOW_SANDBOX_AGE_VERIFY="true",
        ALLOW_DEV_MFA_BYPASS="true",
    )
    try:
        problems = validate_settings(get_settings())
        joined = " ".join(problems)
        assert "SQLite" in joined
        assert "http" in joined
        assert "ALLOW_SANDBOX_AGE_VERIFY" in joined
        assert "ALLOW_DEV_MFA_BYPASS" in joined
    finally:
        get_settings.cache_clear()


def test_staging_rejects_live_payments_without_attestation(monkeypatch):
    _staging_env(
        monkeypatch,
        PAYMENTS_ENABLED="true",
        PAYMENT_PROVIDER="stripe",
        STRIPE_SECRET_KEY="sk_test_not_attested",
        PAYMENTS_PROCESSOR_ATTESTED="false",
    )
    try:
        problems = validate_settings(get_settings())
        assert any("PAYMENTS_PROCESSOR_ATTESTED" in item for item in problems)
    finally:
        get_settings.cache_clear()


def test_staging_rejects_comfyui_until_gpu_host(monkeypatch):
    _staging_env(monkeypatch, GENERATION_BACKEND="comfyui")
    try:
        problems = validate_settings(get_settings())
        assert any("GENERATION_BACKEND" in item for item in problems)
    finally:
        get_settings.cache_clear()


def test_staging_rejects_hotapi_until_vendor_go(monkeypatch):
    _staging_env(monkeypatch, GENERATION_BACKEND="hotapi")
    try:
        problems = validate_settings(get_settings())
        assert any("GENERATION_BACKEND" in item for item in problems)
    finally:
        get_settings.cache_clear()


def test_assert_runtime_safe_raises(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        try:
            assert_runtime_safe(get_settings())
            assert False, "expected BootError"
        except BootError as exc:
            assert "Unsafe" in str(exc)
    finally:
        get_settings.cache_clear()


def test_ready_ok(client):
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_root_explains_api_not_website(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "This is the API" in res.text
    assert "/health" in res.text
