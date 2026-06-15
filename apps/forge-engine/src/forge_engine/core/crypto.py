"""Symmetric encryption for credentials at rest.

Design intent (P0 audit fix):
- Social-publish OAuth tokens were kept in RAM only and lost on restart. We now
  persist them encrypted on disk so a leaked `social_credentials.enc` file is
  useless without the master key.
- The master key never lives next to the ciphertext. Priority:
    1. ``FORGE_SECRET_KEY`` env var — one or more comma-separated Fernet keys.
       The first is used to *encrypt*; all are tried to *decrypt* (enables
       zero-downtime key rotation via ``MultiFernet``).
    2. A locally-generated key file at ``LIBRARY_PATH/.secret.key`` (mode 0600),
       created on first use. Good enough for a personal/family-LAN service where
       the threat model is "someone copied the library folder", not "root on the
       host". Set ``FORGE_SECRET_KEY`` to harden further (e.g. inject from a
       secrets manager and never write the key to disk).

We use Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from `cryptography`.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)

KEY_FILENAME = ".secret.key"
_ENV_KEY = "FORGE_SECRET_KEY"


class CryptoError(RuntimeError):
    """Raised when encryption/decryption cannot proceed (bad key, corruption)."""


def _key_file() -> Path:
    return settings.LIBRARY_PATH / KEY_FILENAME


def _load_or_create_file_key() -> bytes:
    """Return the on-disk master key, generating a 0600 file on first use."""
    path = _key_file()
    if path.exists():
        key = path.read_bytes().strip()
        if not key:
            raise CryptoError(f"Empty key file at {path}; refusing to overwrite.")
        return key

    key = Fernet.generate_key()
    # O_EXCL guards against a race where two workers create it at once; the
    # loser falls back to reading what the winner wrote.
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_bytes().strip()
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    logger.info("Generated new credential master key at %s (mode 0600)", path)
    return key


def _build_fernet() -> MultiFernet:
    """Assemble the active MultiFernet from env keys and/or the file key."""
    keys: list[Fernet] = []

    env_val = os.environ.get(_ENV_KEY, "").strip()
    if env_val:
        for raw in (k.strip() for k in env_val.split(",")):
            if not raw:
                continue
            try:
                keys.append(Fernet(raw.encode() if isinstance(raw, str) else raw))
            except (ValueError, TypeError) as exc:
                raise CryptoError(
                    f"{_ENV_KEY} contains an invalid Fernet key (must be 32 "
                    "url-safe base64-encoded bytes)."
                ) from exc

    # Always append the file key as a decrypt fallback so flipping FORGE_SECRET_KEY
    # on later does not orphan data written under the file key. When no env key is
    # set, the file key is the primary (first) key and thus the encrypt key.
    try:
        keys.append(Fernet(_load_or_create_file_key()))
    except CryptoError:
        if not keys:
            raise
        logger.warning("File master key unavailable; using %s only.", _ENV_KEY)

    if not keys:
        raise CryptoError("No usable encryption key could be assembled.")
    return MultiFernet(keys)


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    return _build_fernet()


def reset_cache() -> None:
    """Forget the cached cipher. Call after changing keys (tests, rotation)."""
    _fernet.cache_clear()


def encrypt_str(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning a url-safe base64 token (str)."""
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_str(token: str) -> str:
    """Decrypt a token produced by :func:`encrypt_str`.

    Raises :class:`CryptoError` if the token is corrupt or no key matches.
    """
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise CryptoError("Could not decrypt token (wrong key or corrupt data).") from exc
