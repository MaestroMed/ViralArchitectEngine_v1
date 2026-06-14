"""API key model — used to gate the public /v1 API surface when the engine
binds to LAN (mode requis pour que l'app iOS atteigne le moteur)."""

import secrets
import uuid
from datetime import datetime
from hashlib import sha256

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from forge_engine.core.database import Base


def hash_key(raw: str) -> str:
    """Constant-output SHA-256 hex of a raw key. We never store the raw key."""
    return sha256(raw.encode("utf-8")).hexdigest()


def generate_key() -> str:
    """Generate a fresh URL-safe API key (~256 bits of entropy)."""
    # 32 bytes → 43 chars base64. Prefix lets us spot accidental commits.
    return "forge_" + secrets.token_urlsafe(32)


class ApiKey(Base):
    """A named API key. The raw key is shown ONCE at creation; only the hash
    is persisted, so a leaked DB doesn't leak usable keys."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # Human label (e.g. "iPhone Air — etostark__").
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    # SHA-256 of the raw key. 64 hex chars.
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Public representation. Never includes the hash or any key material."""
        return {
            "id": self.id,
            "label": self.label,
            "createdAt": self.created_at.isoformat(),
            "lastUsedAt": self.last_used_at.isoformat() if self.last_used_at else None,
            "revokedAt": self.revoked_at.isoformat() if self.revoked_at else None,
        }
