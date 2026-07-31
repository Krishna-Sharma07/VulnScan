import pytest

from app.core.config import Settings
from app.core.secrets import EnvSecretsProvider, _load_provider, require_secret


def test_env_secrets_provider_reads_from_environment(monkeypatch):
    monkeypatch.setenv("SOME_TEST_SECRET", "top-secret-value")
    assert EnvSecretsProvider().get("SOME_TEST_SECRET") == "top-secret-value"


def test_env_secrets_provider_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_UNSET_TEST_SECRET", raising=False)
    assert EnvSecretsProvider().get("SOME_UNSET_TEST_SECRET") is None


def test_require_secret_returns_value_when_present(monkeypatch):
    monkeypatch.setenv("SOME_TEST_SECRET", "top-secret-value")
    assert require_secret("SOME_TEST_SECRET") == "top-secret-value"


@pytest.mark.parametrize("missing_value", [None, ""])
def test_require_secret_raises_when_missing_or_blank(monkeypatch, missing_value):
    if missing_value is None:
        monkeypatch.delenv("SOME_UNSET_TEST_SECRET", raising=False)
    else:
        monkeypatch.setenv("SOME_UNSET_TEST_SECRET", missing_value)
    with pytest.raises(RuntimeError, match="Missing required secret 'SOME_UNSET_TEST_SECRET'"):
        require_secret("SOME_UNSET_TEST_SECRET")


def test_load_provider_defaults_to_env(monkeypatch):
    monkeypatch.delenv("SECRETS_PROVIDER", raising=False)
    assert isinstance(_load_provider(), EnvSecretsProvider)


def test_load_provider_accepts_env_case_insensitively(monkeypatch):
    monkeypatch.setenv("SECRETS_PROVIDER", "ENV")
    assert isinstance(_load_provider(), EnvSecretsProvider)


def test_load_provider_raises_for_unregistered_provider(monkeypatch):
    monkeypatch.setenv("SECRETS_PROVIDER", "aws-secrets-manager")
    with pytest.raises(RuntimeError, match="no registered implementation"):
        _load_provider()


def test_settings_refuses_to_start_without_secret_key(monkeypatch):
    monkeypatch.setenv("AUTH_COOKIE_ENCRYPTION_KEY", "some-fernet-key")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Missing required secret 'SECRET_KEY'"):
        Settings()


def test_settings_refuses_to_start_without_auth_cookie_encryption_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "some-jwt-signing-key")
    monkeypatch.delenv("AUTH_COOKIE_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Missing required secret 'AUTH_COOKIE_ENCRYPTION_KEY'"):
        Settings()
