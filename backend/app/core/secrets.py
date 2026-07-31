import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv

# Populates os.environ from backend/.env in local dev (no-op in CI/production,
# where the real env vars are already set directly). pydantic-settings'
# env_file=".env" on Settings does its own separate parse of the same file
# for regular config fields - this is the parallel load needed so
# EnvSecretsProvider, which reads os.environ directly, sees it too.
load_dotenv()


class SecretsProvider(ABC):
    """Where real secrets (JWT signing key, encryption keys - as opposed to
    plain app config like timeouts or image names) come from. Call sites
    never read os.environ directly for a secret; they go through
    require_secret() below, so swapping the backend later (a real KMS or
    secrets manager, once one is chosen) means adding one class here, not
    touching every place a secret is used."""

    @abstractmethod
    def get(self, name: str) -> str | None: ...


class EnvSecretsProvider(SecretsProvider):
    """Reads from process environment variables - populated from
    backend/.env in local dev (via the load_dotenv() call above) or set
    directly in CI/production. The only provider implemented today; no
    KMS/secrets-manager account exists yet for this project."""

    def get(self, name: str) -> str | None:
        return os.environ.get(name)


def _load_provider() -> SecretsProvider:
    name = os.environ.get("SECRETS_PROVIDER", "env").lower()
    if name == "env":
        return EnvSecretsProvider()
    raise RuntimeError(
        f"SECRETS_PROVIDER={name!r} has no registered implementation. "
        "Only 'env' exists today - add a SecretsProvider subclass in "
        "app/core/secrets.py to wire up a real one."
    )


_provider = _load_provider()


def require_secret(name: str) -> str:
    """Fetch a required secret, failing fast and loudly at startup if it's
    missing - no silent fallback to an insecure built-in default."""
    value = _provider.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required secret '{name}'. Set it as an environment "
            f"variable (see backend/.env.example) before starting the app."
        )
    return value
