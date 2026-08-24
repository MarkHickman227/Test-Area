from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "PrivateCanvas"
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    secret_key: str = "dev-secret-change-me"
    encryption_key: str = ""

    database_url: str = "sqlite+pysqlite:///./data/privatecanvas.db"
    redis_url: str = ""

    storage_backend: Literal["local", "minio"] = "local"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "privatecanvas-outputs"
    minio_secure: bool = False
    storage_local_path: str = "./data/storage"

    mail_backend: Literal["console", "smtp"] = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "noreply@localhost"
    mail_console: bool = True

    age_verification_provider: str = "sandbox"
    age_verification_webhook_secret: str = "dev-webhook-secret"
    allow_sandbox_age_verify: bool = True

    payments_enabled: bool = False
    job_execution: Literal["inline", "celery"] = "inline"
    require_mfa_privileged: bool = True
    allow_dev_mfa_bypass: bool = True

    dev_admin_email: str = "admin@example.com"
    dev_admin_password: str = "dev-admin-password"
    dev_user_email: str = "adult@example.com"
    dev_user_password: str = "dev-user-password"

    signed_url_ttl_seconds: int = 120
    session_ttl_seconds: int = 86400
    queue_max_depth: int = 20
    job_timeout_seconds: int = 180
    promotional_grant_credits: int = 40

    csrf_cookie_name: str = "pc_csrf"
    session_cookie_name: str = "pc_session"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    current_terms_version: str = "tos-2026-08-01"
    current_privacy_version: str = "privacy-2026-08-01"
    current_content_policy_version: str = "content-2026-08-01"
    current_age_policy_version: str = "age-2026-08-01"
    pricing_rule_version: str = "pricing-v1"

    capture_on: Literal["running", "completed"] = "running"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_dev(self) -> bool:
        return self.app_env in {"development", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
