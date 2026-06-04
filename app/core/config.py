from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=True, validation_alias="DEBUG")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    database_url: str = Field(
        default="sqlite:///./data/linkedin_agent.db",
        validation_alias="DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    linkedin_client_id: str = Field(default="", validation_alias="LINKEDIN_CLIENT_ID")
    linkedin_client_secret: str = Field(default="", validation_alias="LINKEDIN_CLIENT_SECRET")
    linkedin_redirect_uri: str = Field(default="", validation_alias="LINKEDIN_REDIRECT_URI")
    linkedin_scopes: str = Field(
        default="openid profile w_member_social",
        validation_alias="LINKEDIN_SCOPES",
    )

    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="CELERY_RESULT_BACKEND",
    )

    session_cookie_name: str = Field(
        default="linkedin_agent_session",
        validation_alias="SESSION_COOKIE_NAME",
    )
    session_cookie_secure: bool = Field(default=False, validation_alias="SESSION_COOKIE_SECURE")
    session_ttl_hours: int = Field(default=24, validation_alias="SESSION_TTL_HOURS", ge=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def linkedin_configured(self) -> bool:
        return bool(
            self.linkedin_client_id
            and self.linkedin_client_secret
            and self.linkedin_redirect_uri
        )

    @property
    def scope_list(self) -> list[str]:
        return [scope for scope in self.linkedin_scopes.split() if scope]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
