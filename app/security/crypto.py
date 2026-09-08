"""Encrypt/decrypt hotel API keys with Fernet.

The master key comes from the MASTER_ENCRYPTION_KEY environment variable only.
Error messages must never include key material (raw or encrypted).
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CryptoError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = settings.master_encryption_key
    if not key:
        raise CryptoError("MASTER_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except ValueError:
        raise CryptoError("MASTER_ENCRYPTION_KEY is not a valid Fernet key") from None


def encrypt_key(raw_key: str) -> str:
    return _fernet().encrypt(raw_key.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise CryptoError(
            "Failed to decrypt API key — was it encrypted with a different master key?"
        ) from None
