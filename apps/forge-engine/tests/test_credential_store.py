"""Tests for the encrypted social credential store + service wiring."""

import stat
from datetime import datetime

import pytest

from forge_engine.core import crypto
from forge_engine.core.config import settings
from forge_engine.services.credential_store import CredentialStore
from forge_engine.services.social_publish import (
    Platform,
    PlatformCredentials,
    SocialPublishService,
)


@pytest.fixture(autouse=True)
def isolated_library(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "LIBRARY_PATH", tmp_path)
    monkeypatch.delenv("FORGE_SECRET_KEY", raising=False)
    crypto.reset_cache()
    yield
    crypto.reset_cache()


def test_save_load_roundtrip(tmp_path):
    store = CredentialStore(tmp_path / "creds.enc")
    records = [
        {"platform": "youtube", "access_token": "yt-tok", "username": "etostark"},
        {"platform": "tiktok", "access_token": "tt-tok", "refresh_token": "r"},
    ]
    store.save(records)
    assert store.load() == records


def test_ciphertext_does_not_contain_plaintext(tmp_path):
    store = CredentialStore(tmp_path / "creds.enc")
    store.save([{"platform": "youtube", "access_token": "SUPER-SECRET-TOKEN"}])
    raw = (tmp_path / "creds.enc").read_bytes()
    assert b"SUPER-SECRET-TOKEN" not in raw


def test_file_mode_is_0600(tmp_path):
    store = CredentialStore(tmp_path / "creds.enc")
    store.save([{"platform": "youtube", "access_token": "t"}])
    mode = stat.S_IMODE((tmp_path / "creds.enc").stat().st_mode)
    assert mode == 0o600


def test_missing_file_returns_empty(tmp_path):
    assert CredentialStore(tmp_path / "absent.enc").load() == []


def test_corrupt_file_returns_empty_not_raises(tmp_path):
    path = tmp_path / "creds.enc"
    path.write_text("this-is-not-a-valid-fernet-token")
    assert CredentialStore(path).load() == []


def test_wrong_key_returns_empty(tmp_path, monkeypatch):
    store = CredentialStore(tmp_path / "creds.enc")
    store.save([{"platform": "youtube", "access_token": "t"}])
    # Rotate to a brand-new key with NO fallback to the original file key.
    from cryptography.fernet import Fernet

    monkeypatch.setenv("FORGE_SECRET_KEY", Fernet.generate_key().decode())
    # Remove the file key so it cannot serve as a decrypt fallback.
    (tmp_path / crypto.KEY_FILENAME).unlink()
    crypto.reset_cache()
    assert CredentialStore(tmp_path / "creds.enc").load() == []


def test_platform_credentials_record_roundtrip():
    cred = PlatformCredentials(
        platform=Platform.YOUTUBE,
        access_token="tok",
        refresh_token="ref",
        expires_at=datetime(2026, 1, 2, 3, 4, 5),
        user_id="uid",
        username="etostark",
    )
    restored = PlatformCredentials.from_record(cred.to_record())
    assert restored == cred


def test_from_record_rejects_malformed():
    assert PlatformCredentials.from_record({"platform": "nope"}) is None
    assert PlatformCredentials.from_record({"platform": "youtube"}) is None
    assert (
        PlatformCredentials.from_record(
            {"platform": "youtube", "access_token": ""}
        )
        is None
    )


def test_service_persists_and_reloads(tmp_path):
    store_path = tmp_path / "creds.enc"
    svc = SocialPublishService(store=CredentialStore(store_path))
    svc.credentials[Platform.YOUTUBE] = PlatformCredentials(
        platform=Platform.YOUTUBE, access_token="tok", username="etostark"
    )
    svc._persist()

    # A fresh service sharing the same store restores the credential.
    reborn = SocialPublishService(store=CredentialStore(store_path))
    assert Platform.YOUTUBE in reborn.credentials
    assert reborn.credentials[Platform.YOUTUBE].access_token == "tok"


@pytest.mark.asyncio
async def test_disconnect_persists_removal(tmp_path):
    store_path = tmp_path / "creds.enc"
    svc = SocialPublishService(store=CredentialStore(store_path))
    svc.credentials[Platform.TIKTOK] = PlatformCredentials(
        platform=Platform.TIKTOK, access_token="tok"
    )
    svc._persist()

    assert await svc.disconnect_account("tiktok") is True
    # The removal must be durable.
    reborn = SocialPublishService(store=CredentialStore(store_path))
    assert Platform.TIKTOK not in reborn.credentials
