from cryptography.fernet import Fernet

from app.core.config import settings

_fernet = Fernet(settings.auth_cookie_encryption_key.encode())


def encrypt_secret(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Raises InvalidToken if `token` wasn't produced by encrypt_secret with
    this same key - callers should let that propagate rather than silently
    treating a corrupt/foreign value as a usable cookie."""
    return _fernet.decrypt(token.encode()).decode()
