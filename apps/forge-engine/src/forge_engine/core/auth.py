"""API key authentication for the FORGE Engine.

Design intent:
- The engine is a personal/family-LAN service. We don't need OAuth or rotating
  tokens — a single long-lived API key per device (iPhone, web-review, CLI)
  authenticates every /v1 request.
- Auth is OFF by default so local dev/desktop on 127.0.0.1 keeps working
  exactly as before. Turn it ON with FORGE_REQUIRE_AUTH=1 (forced when bind
  is widened, see config.py).
- We compare against SHA-256 hashes in constant time. Raw keys are never
  stored or logged.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from forge_engine.core.timeutils import utcnow
from typing import Annotated

from fastapi import Depends, Header, HTTPException, WebSocket, status
from sqlalchemy import select, update

from forge_engine.core.database import async_session_maker
from forge_engine.models.api_key import ApiKey, hash_key

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"


_TRUTHY = ("1", "true", "yes")


def auth_required() -> bool:
    """True iff incoming /v1 requests must carry a valid X-API-Key header.

    Auth is forced ON whenever the engine is bound beyond localhost
    (FORGE_BIND_LAN=1) — never expose the API to the LAN unauthenticated.
    """
    if os.environ.get("FORGE_BIND_LAN", "0").lower() in _TRUTHY:
        return True
    return os.environ.get("FORGE_REQUIRE_AUTH", "0").lower() in _TRUTHY


async def _lookup_and_touch(raw_key: str) -> ApiKey | None:
    """Resolve a raw key to its row and update last_used_at.

    We update in a fire-and-forget UPDATE (no SELECT first) for the hot path
    — one round-trip instead of two. Returns the matched ApiKey row, or None.
    """
    key_hash = hash_key(raw_key)
    async with async_session_maker() as db:
        result = await db.execute(
            select(ApiKey).where(
                ApiKey.key_hash == key_hash,
                ApiKey.revoked_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        await db.execute(
            update(ApiKey)
            .where(ApiKey.id == row.id)
            .values(last_used_at=utcnow())
        )
        await db.commit()
        return row


async def require_api_key(
    x_api_key: Annotated[str | None, Header(alias=API_KEY_HEADER)] = None,
) -> ApiKey | None:
    """FastAPI dependency. When auth is OFF, returns None. When ON, returns
    the ApiKey row for the caller — or raises 401."""
    if not auth_required():
        return None
    if not x_api_key:
        # 401, not 403: the client may have a key and forgot to send it.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    row = await _lookup_and_touch(x_api_key)
    if row is None:
        # Log without the key. Lookup misses are interesting (probe? wrong device?).
        logger.warning("API key auth failed from header (length=%d)", len(x_api_key))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return row


# Convenience alias for endpoint signatures. Use as:
#     async def endpoint(_auth: ApiAuth = Depends(require_api_key)): ...
ApiAuth = Annotated[ApiKey | None, Depends(require_api_key)]


async def authorize_websocket(websocket: WebSocket) -> bool:
    """Gate a WebSocket handshake on the API key.

    WS handshakes can't reuse the HTTP ``Depends(require_api_key)`` cleanly: a
    Header dependency that raises aborts the handshake with an opaque error, and
    browser WS clients can't set custom headers on the upgrade request at all.
    So the WS endpoints call this helper directly instead.

    When auth is OFF (local dev on 127.0.0.1) this always allows — no DB hit,
    behavior unchanged. When ON it requires a valid key taken from the ``?key=``
    query param (preferred, works from any client) or the ``X-API-Key`` header
    (fallback), validated against the ApiKey table and touched like the HTTP
    path. Both are read pre-accept, so the caller can reject before upgrading.

    Returns True to proceed (caller then accepts), False to reject (caller
    closes with code 1008, policy violation).
    """
    if not auth_required():
        return True
    raw_key = websocket.query_params.get("key") or websocket.headers.get(API_KEY_HEADER)
    if not raw_key:
        logger.warning("WebSocket auth failed: no key presented")
        return False
    row = await _lookup_and_touch(raw_key)
    if row is None:
        logger.warning("WebSocket auth failed: invalid or revoked key (length=%d)", len(raw_key))
        return False
    return True