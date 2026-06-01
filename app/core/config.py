from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    debug: bool = True
    secret_key: str = "change-me"

    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"

    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_uri: str = ""

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
