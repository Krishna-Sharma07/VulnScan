from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized app configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24

    # Database
    database_url: str = "postgresql://vulnscan:vulnscan@localhost:5432/vulnscan"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Docker
    docker_scanner_image: str = "vulnscan/zap-scanner:latest"
    scan_timeout_seconds: int = 1800  # 30 min hard cap per scan container

    # Domain verification
    verification_txt_prefix: str = "vulnscan-verify"


settings = Settings()
