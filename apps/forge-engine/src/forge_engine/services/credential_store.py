"""Encrypted at-rest store for social-publish OAuth credentials.

The store is a single encrypted JSON blob at ``LIBRARY_PATH/social_credentials.enc``.
It is intentionally decoupled from the ``PlatformCredentials`` dataclass (it only
deals in plain ``list[dict]``) to avoid an import cycle with
``social_publish``; the service owns the dataclass⇄dict mapping.

Failure policy: reads never raise. A missing/corrupt/unreadable file yields an
empty list and a warning — losing cached tokens just forces a reconnect, which
is far less bad than crashing the engine on boot.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from forge_engine.core.config import settings
from forge_engine.core.crypto import CryptoError, decrypt_str, encrypt_str

logger = logging.getLogger(__name__)

STORE_FILENAME = "social_credentials.enc"


class CredentialStore:
    """Persist/restore a list of credential records, encrypted at rest."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (settings.LIBRARY_PATH / STORE_FILENAME)

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> list[dict]:
        """Return the stored records, or ``[]`` if none/unreadable."""
        if not self._path.exists():
            return []
        try:
            token = self._path.read_text(encoding="ascii").strip()
            if not token:
                return []
            data = json.loads(decrypt_str(token))
        except CryptoError:
            logger.warning(
                "Could not decrypt %s (key changed or file corrupt). "
                "Ignoring; reconnect social accounts to repopulate.",
                self._path.name,
            )
            return []
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            logger.warning("Could not read %s: %s", self._path.name, exc)
            return []

        if not isinstance(data, list):
            logger.warning("Unexpected shape in %s; ignoring.", self._path.name)
            return []
        return data

    def save(self, records: list[dict]) -> None:
        """Encrypt and atomically write the records to disk (mode 0600)."""
        payload = encrypt_str(json.dumps(records, separators=(",", ":")))
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        # Create the temp file with restrictive perms from the start so the
        # ciphertext is never briefly world-readable.
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload.encode("ascii"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, self._path)

    def clear(self) -> None:
        """Remove the on-disk store, if present."""
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
