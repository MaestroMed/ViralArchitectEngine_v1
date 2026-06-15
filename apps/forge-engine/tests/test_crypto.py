"""Tests for core/crypto — credential encryption at rest."""

import os
import stat

import pytest
from cryptography.fernet import Fernet

from forge_engine.core import crypto
from forge_engine.core.config import settings


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    """Point the key file at a temp dir and reset the cipher cache per test."""
    monkeypatch.setattr(settings, "LIBRARY_PATH", tmp_path)
    monkeypatch.delenv("FORGE_SECRET_KEY", raising=False)
    crypto.reset_cache()
    yield
    crypto.reset_cache()


def test_roundtrip_with_generated_file_key():
    token = crypto.encrypt_str("hunter2")
    assert token != "hunter2"
    assert crypto.decrypt_str(token) == "hunter2"


def test_key_file_created_with_0600(tmp_path):
    crypto.encrypt_str("x")
    key_file = tmp_path / crypto.KEY_FILENAME
    assert key_file.exists()
    mode = stat.S_IMODE(key_file.stat().st_mode)
    assert mode == 0o600


def test_key_file_is_stable_across_cache_resets():
    a = crypto.encrypt_str("payload")
    crypto.reset_cache()
    # Same on-disk key must still decrypt what we wrote before.
    assert crypto.decrypt_str(a) == "payload"


def test_env_key_takes_precedence(monkeypatch):
    env_key = Fernet.generate_key().decode()
    monkeypatch.setenv("FORGE_SECRET_KEY", env_key)
    crypto.reset_cache()
    token = crypto.encrypt_str("from-env")
    # A cipher built from only the env key must be able to decrypt it.
    assert Fernet(env_key).decrypt(token.encode()).decode() == "from-env"


def test_invalid_env_key_raises(monkeypatch):
    monkeypatch.setenv("FORGE_SECRET_KEY", "not-a-valid-fernet-key")
    crypto.reset_cache()
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt_str("x")


def test_decrypt_corrupt_token_raises():
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt_str("garbage-not-a-token")


def test_rotation_env_primary_file_fallback(monkeypatch, tmp_path):
    # Write under the file key first.
    legacy = crypto.encrypt_str("legacy-secret")
    # Now introduce an env key as the new primary; the file key stays as a
    # decrypt fallback, so old data is still readable.
    new_key = Fernet.generate_key().decode()
    monkeypatch.setenv("FORGE_SECRET_KEY", new_key)
    crypto.reset_cache()
    assert crypto.decrypt_str(legacy) == "legacy-secret"
    # New writes use the new primary key.
    fresh = crypto.encrypt_str("fresh-secret")
    assert Fernet(new_key).decrypt(fresh.encode()).decode() == "fresh-secret"
