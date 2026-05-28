from functools import lru_cache

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

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-latest",
        validation_alias="ANTHROPIC_MODEL",
    )

    perplexity_api_key: str | None = Field(default=None, validation_alias="PERPLEXITY_API_KEY")
    perplexity_model: str = Field(default="sonar-pro", validation_alias="PERPLEXITY_MODEL")

    telegram_bot_token: str | None = Field(default=None, validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(default=None, validation_alias="TELEGRAM_CHAT_ID")

    scheduler_enabled: bool = Field(default=True, validation_alias="SCHEDULER_ENABLED")
    discovery_interval_minutes: int = Field(
        default=150,
        validation_alias="DISCOVERY_INTERVAL_MINUTES",
        ge=30,
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
    def supabase_rest_url(self) -> str | None:
        if not self.supabase_url:
            return None
        return f"{str(self.supabase_url).rstrip('/')}/rest/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
