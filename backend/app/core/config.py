from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.secrets import require_secret


class Settings(BaseSettings):
    """Centralized app configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    environment: str = "development"
    access_token_expire_minutes: int = 60 * 24

    # secret_key (JWT signing) and auth_cookie_encryption_key (Fernet key
    # encrypting Domain.auth_cookie at rest, a real session credential - see
    # NOTES.md) are real secrets, not config with a safe hardcoded default -
    # both used to have one baked into this file, which meant a deployment
    # that forgot to set the env var would silently sign tokens / encrypt
    # data with a key visible to anyone reading the source. They're loaded
    # via app.core.secrets instead, in model_post_init below, which fails
    # startup loudly if either is missing rather than falling back to
    # something insecure-but-working.
    secret_key: str = ""
    auth_cookie_encryption_key: str = ""

    # Razorpay API keys - key_secret is a real secret (server-side only,
    # used to sign/verify payments); key_id is not sensitive on its own
    # (Razorpay's Checkout.js runs it in the browser by design) but is loaded
    # the same way for consistency and because it still shouldn't have a
    # committed default.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    def model_post_init(self, __context) -> None:
        self.secret_key = require_secret("SECRET_KEY")
        self.auth_cookie_encryption_key = require_secret("AUTH_COOKIE_ENCRYPTION_KEY")
        self.razorpay_key_id = require_secret("RAZORPAY_KEY_ID")
        self.razorpay_key_secret = require_secret("RAZORPAY_KEY_SECRET")

    # Database
    database_url: str = "postgresql://vulnscan:vulnscan@localhost:5432/vulnscan"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Docker
    docker_scanner_image: str = "vulnscan/zap-scanner:latest"
    scan_timeout_seconds: int = 1800  # 30 min hard cap per scan container

    docker_sqlmap_image: str = "vulnscan/sqlmap-scanner:latest"
    sqlmap_timeout_seconds: int = 900  # 15 min hard cap - runs in addition to the ZAP scan above

    docker_code_scanner_image: str = "vulnscan/code-scanner:latest"
    code_scan_timeout_seconds: int = 600  # 10 min hard cap - static analysis only, no network scanning

    # Uploaded code archives are capped well below the container's own
    # uncompressed zip-bomb guard (code-scanner/entrypoint.sh) - rejecting an
    # oversized *compressed* file at the API layer, before it ever reaches a
    # container, is cheaper than let it through and rely on the in-container
    # check alone.
    code_scan_max_upload_bytes: int = 20 * 1024 * 1024  # 20MB

    # Scanner containers are launched as Docker-out-of-Docker siblings of the
    # worker (see NOTES.md section 11) - attaching them to this network lets
    # them resolve other compose services by hostname (e.g. "dvwa"), not just
    # reach the public internet via the default bridge network.
    docker_scan_network: str = "vulnscan-network"

    # Reports
    # Relative to the backend's WORKDIR (/app in the container). api and
    # worker both bind-mount ./backend to /app, so a file the worker writes
    # here is immediately visible to the api process too - no extra volume
    # needed for this one, unlike the scanner container (see NOTES.md).
    reports_dir: str = "reports"

    # Uploaded code archives, spooled to disk between the API request that
    # receives them and the worker task that reads them - same bind-mount-
    # shared-/app-directory pattern reports_dir relies on (see the comment
    # above), just in the opposite direction (api writes, worker reads).
    uploads_dir: str = "uploads"

    # Domain verification
    verification_txt_prefix: str = "vulnscan-verify"


settings = Settings()
