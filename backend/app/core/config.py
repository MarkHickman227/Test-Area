import base64
import json
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    api_cors_origins: str = Field(
        default="http://localhost,http://127.0.0.1",
        validation_alias="API_CORS_ORIGINS",
    )

    supabase_url: AnyHttpUrl | None = Field(default=None, validation_alias="SUPABASE_URL")
    supabase_service_key: str | None = Field(
        default=None,
        validation_alias="SUPABASE_SERVICE_KEY",
    )
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-6",
        validation_alias="ANTHROPIC_MODEL",
    )

    perplexity_api_key: str | None = Field(default=None, validation_alias="PERPLEXITY_API_KEY")
    perplexity_model: str = Field(default="sonar-pro", validation_alias="PERPLEXITY_MODEL")

    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")

    scheduler_enabled: bool = Field(default=True, validation_alias="SCHEDULER_ENABLED")
    discovery_schedule_mode: str = Field(
        default="twice_daily",
        validation_alias="DISCOVERY_SCHEDULE_MODE",
    )
    discovery_times: str = Field(
        default="08:00,20:00",
        validation_alias="DISCOVERY_TIMES",
    )
    discovery_timezone: str = Field(
        default="Europe/London",
        validation_alias="DISCOVERY_TIMEZONE",
    )
    discovery_interval_minutes: int = Field(
        default=720,
        validation_alias="DISCOVERY_INTERVAL_MINUTES",
        ge=30,
    )
    pipeline_trigger_token: str | None = Field(
        default=None,
        validation_alias="PIPELINE_TRIGGER_TOKEN",
    )

    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(
            self.supabase_url
            and str(self.supabase_url) != "https://your-project.supabase.co/"
            and self._has_valid_supabase_service_key()
        )

    @property
    def database_configured(self) -> bool:
        return self._has_real_secret(self.database_url)

    @property
    def anthropic_configured(self) -> bool:
        return self._has_real_secret(self.anthropic_api_key)

    @property
    def perplexity_configured(self) -> bool:
        return self._has_real_secret(self.perplexity_api_key)

    @property
    def discovery_time_list(self) -> list[str]:
        return [chunk.strip() for chunk in self.discovery_times.split(",") if chunk.strip()]

    @property
    def parsed_discovery_times(self):
        from app.services.schedule import parse_discovery_times

        return parse_discovery_times(self.discovery_times)

    @property
    def trigger_token_configured(self) -> bool:
        return self._has_real_secret(self.pipeline_trigger_token)

    @property
    def supabase_rest_url(self) -> str | None:
        if not self.supabase_configured:
            return None
        return f"{str(self.supabase_url).rstrip('/')}/rest/v1"

    @property
    def supabase_project_ref(self) -> str | None:
        if not self.supabase_url:
            return None
        host = urlparse(str(self.supabase_url)).hostname or ""
        suffix = ".supabase.co"
        if not host.endswith(suffix):
            return None
        return host.removesuffix(suffix)

    @staticmethod
    def _has_real_secret(value: str | None) -> bool:
        if not value:
            return False
        normalized = value.strip().lower()
        if not normalized or normalized.startswith("replace-with"):
            return False
        # Treat common .env.example placeholders as unconfigured.
        placeholders = (
            "your-project",
            "project-ref",
            "aws-0-region",
            "replace-with-db-password",
            "your-db-password",
        )
        return not any(token in normalized for token in placeholders)

    def _has_valid_supabase_service_key(self) -> bool:
        if not self._has_real_secret(self.supabase_service_key):
            return False
        key = (self.supabase_service_key or "").strip()
        if key.startswith("sb_secret_"):
            return True

        payload = self._decode_jwt_payload(key)
        if not payload:
            return False
        if payload.get("role") != "service_role":
            return False

        key_ref = payload.get("ref")
        project_ref = self.supabase_project_ref
        return bool(key_ref and project_ref and key_ref == project_ref)

    @staticmethod
    def _decode_jwt_payload(token: str) -> dict[str, object] | None:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
            payload = json.loads(decoded)
        except (ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
