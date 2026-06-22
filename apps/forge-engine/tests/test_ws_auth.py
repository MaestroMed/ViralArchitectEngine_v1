"""WebSocket auth tests — the WS handshake must be gated by the API key exactly
when HTTP auth is required, and stay fully open for local dev when it isn't.

Covers the helper (core.auth.authorize_websocket), the real route wiring through
a TestClient, and that a connected (authed) client receives broadcasts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.websockets import WebSocketDisconnect


@pytest_asyncio.fixture
async def isolated_db(monkeypatch, tmp_path) -> AsyncIterator[None]:
    """Brand-new SQLite DB per test, wired into the engine module globals.
    Mirrors the fixture in test_auth.py so the two suites stay independent."""
    db_path = tmp_path / "ws_auth_test.db"

    from forge_engine.core import database as db_module

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "async_session_maker", sessionmaker)
    from forge_engine.core import auth as auth_module
    monkeypatch.setattr(auth_module, "async_session_maker", sessionmaker)

    async with engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.create_all)

    yield

    await engine.dispose()


def _fake_ws(*, key: str | None = None, header: str | None = None) -> SimpleNamespace:
    """A stand-in WebSocket exposing just what authorize_websocket reads."""
    return SimpleNamespace(
        query_params={"key": key} if key is not None else {},
        headers={"X-API-Key": header} if header is not None else {},
    )


async def _seed_key(label: str = "test"):
    from forge_engine.core.database import async_session_maker
    from forge_engine.models.api_key import ApiKey, generate_key, hash_key

    raw = generate_key()
    async with async_session_maker() as db:
        db.add(ApiKey(label=label, key_hash=hash_key(raw)))
        await db.commit()
    return raw


# --- helper unit tests -------------------------------------------------------

@pytest.mark.asyncio
async def test_authorize_open_when_auth_off(monkeypatch):
    """Auth off → always allowed, no key, no DB hit (local dev unchanged)."""
    monkeypatch.delenv("FORGE_REQUIRE_AUTH", raising=False)
    monkeypatch.delenv("FORGE_BIND_LAN", raising=False)
    from forge_engine.core.auth import authorize_websocket

    assert await authorize_websocket(_fake_ws()) is True


@pytest.mark.asyncio
async def test_authorize_rejects_missing_key(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")
    from forge_engine.core.auth import authorize_websocket

    assert await authorize_websocket(_fake_ws()) is False


@pytest.mark.asyncio
async def test_authorize_rejects_bad_key(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")
    from forge_engine.core.auth import authorize_websocket

    assert await authorize_websocket(_fake_ws(key="nope")) is False
    assert await authorize_websocket(_fake_ws(header="nope")) is False


@pytest.mark.asyncio
async def test_authorize_accepts_valid_key_via_query_and_header(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")
    from forge_engine.core.auth import authorize_websocket

    raw = await _seed_key()
    assert await authorize_websocket(_fake_ws(key=raw)) is True
    assert await authorize_websocket(_fake_ws(header=raw)) is True


@pytest.mark.asyncio
async def test_authorize_touches_last_used(isolated_db, monkeypatch):
    from sqlalchemy import select

    from forge_engine.core.database import async_session_maker
    from forge_engine.models.api_key import ApiKey, hash_key

    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")
    from forge_engine.core.auth import authorize_websocket

    raw = await _seed_key()
    assert await authorize_websocket(_fake_ws(key=raw)) is True

    async with async_session_maker() as db:
        row = (await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))).scalar_one()
    assert row.last_used_at is not None


# --- route wiring (TestClient) ----------------------------------------------

def _make_ws_app() -> FastAPI:
    """App mirroring main.py's wiring: WS router mounted at /v1 with NO global
    auth dependency — it self-authenticates via authorize_websocket()."""
    from forge_engine.api.v1.endpoints import websockets

    app = FastAPI()
    app.include_router(websockets.router, prefix="/v1", tags=["Real-time"])
    return app


def test_ws_open_when_auth_off(monkeypatch):
    monkeypatch.delenv("FORGE_REQUIRE_AUTH", raising=False)
    monkeypatch.delenv("FORGE_BIND_LAN", raising=False)

    client = TestClient(_make_ws_app())
    with client.websocket_connect("/v1/ws") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "PONG"}


@pytest.mark.asyncio
async def test_ws_rejects_without_key(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_BIND_LAN", "1")  # forces auth on

    client = TestClient(_make_ws_app())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/v1/ws") as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_ws_rejects_bad_key(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_BIND_LAN", "1")

    client = TestClient(_make_ws_app())
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/v1/ws?key=nope") as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_ws_accepts_valid_key(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_BIND_LAN", "1")
    raw = await _seed_key("ws-client")

    client = TestClient(_make_ws_app())
    with client.websocket_connect(f"/v1/ws?key={raw}") as ws:
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "PONG"}


# --- broadcast delivery ------------------------------------------------------

@pytest.mark.asyncio
async def test_connected_client_receives_job_update():
    """A connected client is in manager.clients and gets JOB_UPDATE broadcasts.
    This is the same broadcast() path the JobManager listener drives in prod."""
    from forge_engine.api.v1.endpoints.websockets import ConnectionManager, WSClient

    sent: list[dict] = []

    class FakeWS:
        async def send_json(self, msg):
            sent.append(msg)

    mgr = ConnectionManager()
    fake = FakeWS()
    mgr.clients[fake] = WSClient(websocket=fake)

    await mgr.broadcast({"type": "JOB_UPDATE", "payload": {"id": "abc", "progress": 42.0}})

    assert sent == [{"type": "JOB_UPDATE", "payload": {"id": "abc", "progress": 42.0}}]
