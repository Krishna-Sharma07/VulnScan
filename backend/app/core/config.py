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

    docker_sqlmap_image: str = "vulnscan/sqlmap-scanner:latest"
    sqlmap_timeout_seconds: int = 900  # 15 min hard cap - runs in addition to the ZAP scan above

    # Reports
    # Relative to the backend's WORKDIR (/app in the container). api and
    # worker both bind-mount ./backend to /app, so a file the worker writes
    # here is immediately visible to the api process too - no extra volume
    # needed for this one, unlike the scanner container (see NOTES.md).
    reports_dir: str = "reports"

    # Domain verification
    verification_txt_prefix: str = "vulnscan-verify"


settings = Settings()
