import pytest

from app.config import settings
from app.security.crypto import CryptoError, decrypt_key, encrypt_key


def test_round_trip():
    encrypted = encrypt_key("sk-super-secret")
    assert encrypted != "sk-super-secret"
    assert decrypt_key(encrypted) == "sk-super-secret"


def test_missing_master_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "master_encryption_key", "")
    with pytest.raises(CryptoError):
        encrypt_key("sk-anything")


def test_invalid_master_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "master_encryption_key", "not-a-fernet-key")
    with pytest.raises(CryptoError):
        encrypt_key("sk-anything")


def test_wrong_key_material_raises():
    with pytest.raises(CryptoError):
        decrypt_key("gAAAAA-not-a-real-token")


def test_errors_never_contain_key_material(monkeypatch):
    try:
        decrypt_key("gAAAAA-not-a-real-token")
    except CryptoError as exc:
        assert "gAAAAA" not in str(exc)
        assert settings.master_encryption_key not in str(exc)
