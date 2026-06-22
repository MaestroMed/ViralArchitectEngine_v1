"""APNs sender tests — JWT builder + no-op-when-unconfigured behaviour.

These never touch the network and don't require the `h2` package: we verify the
ES256 provider JWT is well-formed (header/claims/signature against a locally
generated EC key) and that the sender is a clean no-op when env is unset.
"""

from __future__ import annotations

import base64
import json

import pytest


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@pytest.fixture
def p8_key(tmp_path):
    """Write a throwaway EC P-256 private key in PEM (.p8 shape) and return its path."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path = tmp_path / "AuthKey_TEST123456.p8"
    path.write_bytes(pem)
    return path, key


def test_load_config_none_when_unset(monkeypatch):
    from forge_engine.services import apns

    for var in (
        "FORGE_APNS_KEY_PATH",
        "FORGE_APNS_KEY_ID",
        "FORGE_APNS_TEAM_ID",
        "FORGE_APNS_BUNDLE_ID",
    ):
        monkeypatch.delenv(var, raising=False)

    assert apns.load_config() is None


def test_load_config_none_when_key_missing(monkeypatch, tmp_path):
    from forge_engine.services import apns

    monkeypatch.setenv("FORGE_APNS_KEY_PATH", str(tmp_path / "nope.p8"))
    monkeypatch.setenv("FORGE_APNS_KEY_ID", "ABC1234567")
    monkeypatch.setenv("FORGE_APNS_TEAM_ID", "ST2RNU2ZX9")
    monkeypatch.setenv("FORGE_APNS_BUNDLE_ID", "com.maestromed.forgelab")
    assert apns.load_config() is None


def test_load_config_ok(monkeypatch, p8_key):
    from forge_engine.services import apns

    path, _ = p8_key
    monkeypatch.setenv("FORGE_APNS_KEY_PATH", str(path))
    monkeypatch.setenv("FORGE_APNS_KEY_ID", "ABC1234567")
    monkeypatch.setenv("FORGE_APNS_TEAM_ID", "ST2RNU2ZX9")
    monkeypatch.setenv("FORGE_APNS_BUNDLE_ID", "com.maestromed.forgelab")
    monkeypatch.setenv("FORGE_APNS_ENV", "sandbox")

    cfg = apns.load_config()
    assert cfg is not None
    assert cfg.key_id == "ABC1234567"
    assert cfg.team_id == "ST2RNU2ZX9"
    assert cfg.bundle_id == "com.maestromed.forgelab"
    assert cfg.use_sandbox is True
    assert cfg.host == "https://api.sandbox.push.apple.com"


def test_env_production_selects_prod_host(monkeypatch, p8_key):
    from forge_engine.services import apns

    path, _ = p8_key
    monkeypatch.setenv("FORGE_APNS_KEY_PATH", str(path))
    monkeypatch.setenv("FORGE_APNS_KEY_ID", "ABC1234567")
    monkeypatch.setenv("FORGE_APNS_TEAM_ID", "ST2RNU2ZX9")
    monkeypatch.setenv("FORGE_APNS_BUNDLE_ID", "com.maestromed.forgelab")
    monkeypatch.setenv("FORGE_APNS_ENV", "production")

    cfg = apns.load_config()
    assert cfg.use_sandbox is False
    assert cfg.host == "https://api.push.apple.com"


def test_build_provider_jwt_structure_and_signature(p8_key):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    from forge_engine.services import apns

    path, key = p8_key
    cfg = apns.ApnsConfig(
        key_path=str(path),
        key_id="ABC1234567",
        team_id="ST2RNU2ZX9",
        bundle_id="com.maestromed.forgelab",
        use_sandbox=True,
    )

    token = apns.build_provider_jwt(cfg, now=1_700_000_000)
    parts = token.split(".")
    assert len(parts) == 3  # header.claims.signature

    header = json.loads(_b64url_decode(parts[0]))
    claims = json.loads(_b64url_decode(parts[1]))
    assert header == {"alg": "ES256", "kid": "ABC1234567"}
    assert claims == {"iss": "ST2RNU2ZX9", "iat": 1_700_000_000}

    # Signature is JOSE raw r||s (64 bytes for P-256), NOT DER — verify it.
    raw = _b64url_decode(parts[2])
    assert len(raw) == 64
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    der = encode_dss_signature(r, s)
    signing_input = (parts[0] + "." + parts[1]).encode("ascii")
    # Raises InvalidSignature if it doesn't verify.
    key.public_key().verify(der, signing_input, ec.ECDSA(hashes.SHA256()))


def test_build_provider_jwt_is_cached(p8_key):
    from forge_engine.services import apns

    path, _ = p8_key
    cfg = apns.ApnsConfig(
        key_path=str(path),
        key_id="CACHEKEY01",
        team_id="ST2RNU2ZX9",
        bundle_id="com.maestromed.forgelab",
        use_sandbox=True,
    )
    apns._jwt_cache.clear()
    t1 = apns.build_provider_jwt(cfg, now=1_700_000_000)
    # 10 minutes later, still inside the 50-min TTL → same token returned.
    t2 = apns.build_provider_jwt(cfg, now=1_700_000_000 + 600)
    assert t1 == t2
    # Past the TTL → a fresh token (new iat).
    t3 = apns.build_provider_jwt(cfg, now=1_700_000_000 + 3601)
    assert t3 != t1


def test_send_alert_noop_when_unconfigured(monkeypatch):
    from forge_engine.services import apns

    for var in (
        "FORGE_APNS_KEY_PATH",
        "FORGE_APNS_KEY_ID",
        "FORGE_APNS_TEAM_ID",
        "FORGE_APNS_BUNDLE_ID",
    ):
        monkeypatch.delenv(var, raising=False)

    # Must return False (no-op) and NOT raise, even with no key configured.
    assert apns.send_alert("deadbeef", title="t", body="b") is False


@pytest.mark.asyncio
async def test_notify_clips_ready_noop_when_unconfigured(monkeypatch):
    from forge_engine.services import apns

    for var in (
        "FORGE_APNS_KEY_PATH",
        "FORGE_APNS_KEY_ID",
        "FORGE_APNS_TEAM_ID",
        "FORGE_APNS_BUNDLE_ID",
    ):
        monkeypatch.delenv(var, raising=False)

    # No DB hit, no push, no exception — returns 0.
    assert await apns.notify_clips_ready("project-123", 7) == 0
