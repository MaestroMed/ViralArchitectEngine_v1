"""Auth layer tests — hashing, env gating, FastAPI integration."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def isolated_db(monkeypatch, tmp_path) -> AsyncIterator[None]:
    """Spin up a brand-new SQLite DB for each test and rewire the engine module's
    globals to point at it. Avoids tests stepping on each other's keys."""
    db_path = tmp_path / "auth_test.db"

    from forge_engine.core import database as db_module

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "async_session_maker", sessionmaker)
    # Modules that imported `async_session_maker` directly also need to pick up
    # the new binding.
    from forge_engine.core import auth as auth_module
    from forge_engine.models import api_key as api_key_module
    monkeypatch.setattr(auth_module, "async_session_maker", sessionmaker)
    # api_key.py only exposes helpers, no session — nothing to patch there.
    _ = api_key_module  # silence linter

    async with engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.create_all)

    yield

    await engine.dispose()


def test_generate_and_hash():
    from forge_engine.models.api_key import generate_key, hash_key

    a = generate_key()
    b = generate_key()
    assert a.startswith("forge_")
    assert a != b  # 256-bit entropy makes collisions a non-issue
    assert hash_key(a) == hash_key(a)  # deterministic
    assert hash_key(a) != hash_key(b)
    assert len(hash_key(a)) == 64  # SHA-256 hex


def test_auth_required_off_by_default(monkeypatch):
    from forge_engine.core.auth import auth_required

    monkeypatch.delenv("FORGE_REQUIRE_AUTH", raising=False)
    monkeypatch.delenv("FORGE_BIND_LAN", raising=False)
    assert auth_required() is False


def test_auth_required_explicit_env(monkeypatch):
    from forge_engine.core.auth import auth_required

    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")
    monkeypatch.delenv("FORGE_BIND_LAN", raising=False)
    assert auth_required() is True

    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "true")
    assert auth_required() is True

    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "0")
    assert auth_required() is False


def test_auth_forced_when_bind_lan(monkeypatch):
    """Critical safety net: never expose a LAN-bound engine without auth."""
    from forge_engine.core.auth import auth_required

    monkeypatch.delenv("FORGE_REQUIRE_AUTH", raising=False)
    monkeypatch.setenv("FORGE_BIND_LAN", "1")
    assert auth_required() is True


def _make_app() -> FastAPI:
    """Tiny FastAPI app with a single protected route, mirroring the real wiring."""
    from forge_engine.core.auth import require_api_key

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/v1/ping")
    async def ping(_auth=Depends(require_api_key)):
        return {"pong": True}

    return app


def test_http_unauthenticated_when_auth_off(monkeypatch):
    """With auth off, /v1 routes succeed without a header."""
    monkeypatch.delenv("FORGE_REQUIRE_AUTH", raising=False)
    monkeypatch.delenv("FORGE_BIND_LAN", raising=False)

    client = TestClient(_make_app())
    r = client.get("/v1/ping")
    assert r.status_code == 200
    assert r.json() == {"pong": True}


@pytest.mark.asyncio
async def test_http_requires_header(isolated_db, monkeypatch):
    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")
    client = TestClient(_make_app())

    # Missing header → 401
    r = client.get("/v1/ping")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers

    # Bogus key → 401
    r = client.get("/v1/ping", headers={"X-API-Key": "nope"})
    assert r.status_code == 401

    # Health is always public
    r = client.get("/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_http_accepts_valid_key_and_records_last_used(isolated_db, monkeypatch):
    from sqlalchemy import select

    from forge_engine.core.database import async_session_maker
    from forge_engine.models.api_key import ApiKey, generate_key, hash_key

    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")

    raw = generate_key()
    async with async_session_maker() as db:
        db.add(ApiKey(label="test", key_hash=hash_key(raw)))
        await db.commit()

    client = TestClient(_make_app())
    r = client.get("/v1/ping", headers={"X-API-Key": raw})
    assert r.status_code == 200

    async with async_session_maker() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
        row = result.scalar_one()
    assert row.last_used_at is not None  # touched by the auth dependency


@pytest.mark.asyncio
async def test_revoked_key_is_rejected(isolated_db, monkeypatch):
    from datetime import datetime

    from sqlalchemy import update

    from forge_engine.core.database import async_session_maker
    from forge_engine.models.api_key import ApiKey, generate_key, hash_key

    monkeypatch.setenv("FORGE_REQUIRE_AUTH", "1")

    raw = generate_key()
    async with async_session_maker() as db:
        row = ApiKey(label="will-revoke", key_hash=hash_key(raw))
        db.add(row)
        await db.commit()
        await db.refresh(row)
        key_id = row.id

    # Use it once successfully, then revoke, then try again.
    client = TestClient(_make_app())
    assert client.get("/v1/ping", headers={"X-API-Key": raw}).status_code == 200

    async with async_session_maker() as db:
        await db.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(revoked_at=datetime.utcnow())
        )
        await db.commit()

    r = client.get("/v1/ping", headers={"X-API-Key": raw})
    assert r.status_code == 401
