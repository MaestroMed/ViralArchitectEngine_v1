"""Mobile clip endpoints — by-date / batch-approve / bundle.zip / cover."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from forge_engine.api.v1.endpoints import clips_mobile
from forge_engine.models.review import ClipQueue


@pytest_asyncio.fixture
async def db_and_app(monkeypatch, tmp_path) -> AsyncIterator[tuple]:
    """Spin up an isolated SQLite DB + a FastAPI app that mounts only the
    clips_mobile router. Avoids touching the global engine."""
    from forge_engine.core import database as db_module

    db_path = tmp_path / "clips_mobile.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "async_session_maker", sessionmaker)
    monkeypatch.setattr(clips_mobile, "async_session_maker", sessionmaker)

    # Make sure every model is registered before create_all.
    from forge_engine.models import (  # noqa: F401
        api_key,
        artifact,
        channel,
        job,
        profile,
        project,
        review,
        segment,
        template,
        training_data,
    )

    async with engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.create_all)

    app = FastAPI()
    app.include_router(clips_mobile.router, prefix="/v1/clips")

    yield sessionmaker, app, tmp_path
    await engine.dispose()


async def _insert_clip(sessionmaker, *, status="pending_review", channel="etostark__", offset_days=0, video_path: Path | None = None, cover_path: Path | None = None, title="hook", hashtags=None, viral_score=85.0) -> str:
    from forge_engine.models.project import Project

    pid = "00000000-0000-0000-0000-000000000001"
    async with sessionmaker() as db:
        # Project FK is required; create once on first call (idempotent).
        existing = await db.get(Project, pid)
        if existing is None:
            db.add(Project(id=pid, name="t", source_path="/tmp/src.mp4", source_filename="src.mp4", status="ready"))
            await db.commit()

        clip = ClipQueue(
            project_id=pid,
            segment_id="seg-1",
            video_path=str(video_path) if video_path else "/tmp/missing.mp4",
            cover_path=str(cover_path) if cover_path else None,
            duration=12.5,
            viral_score=viral_score,
            status=status,
            channel_name=channel,
            title=title,
            description=f"{title} — description",
            hashtags=hashtags or ["forgelab", "etostark"],
            created_at=datetime.utcnow() - timedelta(days=offset_days),
        )
        db.add(clip)
        await db.commit()
        await db.refresh(clip)
        return clip.id


# ─── by-date ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_by_date_isolates_to_day(db_and_app):
    sessionmaker, app, _ = db_and_app
    today = datetime.utcnow().date().isoformat()
    yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

    await _insert_clip(sessionmaker, offset_days=1, title="yesterday")
    await _insert_clip(sessionmaker, offset_days=0, title="today")

    client = TestClient(app)
    r = client.get(f"/v1/clips/by-date?date={yesterday}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["date"] == yesterday
    assert body["count"] == 1
    assert body["items"][0]["title"] == "yesterday"

    r = client.get(f"/v1/clips/by-date?date={today}")
    assert r.json()["count"] == 1


@pytest.mark.asyncio
async def test_by_date_filters_status_and_channel(db_and_app):
    sessionmaker, app, _ = db_and_app
    today = datetime.utcnow().date().isoformat()
    await _insert_clip(sessionmaker, channel="etostark__", status="pending_review", title="A")
    await _insert_clip(sessionmaker, channel="other", status="pending_review", title="B")
    await _insert_clip(sessionmaker, channel="etostark__", status="approved", title="C")

    client = TestClient(app)
    r = client.get(f"/v1/clips/by-date?date={today}&channel=etostark__&status=pending_review")
    assert r.json()["count"] == 1
    assert r.json()["items"][0]["title"] == "A"


def test_by_date_rejects_bad_date(db_and_app):
    _, app, _ = db_and_app
    r = TestClient(app).get("/v1/clips/by-date?date=2026-13-32")
    assert r.status_code == 400


# ─── batch-approve ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_approve_only_flips_pending(db_and_app):
    sessionmaker, app, _ = db_and_app
    a = await _insert_clip(sessionmaker, status="pending_review")
    b = await _insert_clip(sessionmaker, status="pending_review")
    c = await _insert_clip(sessionmaker, status="approved")  # skipped
    missing_id = "00000000-0000-0000-0000-000000000099"

    client = TestClient(app)
    r = client.post("/v1/clips/batch-approve", json={"ids": [a, b, c, missing_id]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["requested"] == 4
    assert body["approved"] == 2
    assert set(body["skipped"]) == {c, missing_id}


def test_batch_approve_rejects_empty(db_and_app):
    _, app, _ = db_and_app
    r = TestClient(app).post("/v1/clips/batch-approve", json={"ids": []})
    assert r.status_code == 422  # pydantic min_length=1


# ─── bundle.zip ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bundle_contains_video_cover_and_metadata(db_and_app):
    sessionmaker, app, tmp_path = db_and_app
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fakevideobytes" * 100)
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"\xFF\xD8\xFF\xE0fakejpeg" + b"\x00" * 50)

    clip_id = await _insert_clip(
        sessionmaker,
        video_path=video,
        cover_path=cover,
        title="Hook qui claque",
        hashtags=["EtoStark", "#viral"],
    )

    r = TestClient(app).get(f"/v1/clips/{clip_id}/bundle.zip")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "clip.mp4" in names
    assert any(n.startswith("cover") for n in names)
    assert "metadata.json" in names

    meta = json.loads(zf.read("metadata.json"))
    assert meta["id"] == clip_id
    assert meta["title"] == "Hook qui claque"
    # Pre-built caption: hashtags rendered with the leading '#', original or added.
    assert "#EtoStark" in meta["caption"]
    assert "#viral" in meta["caption"]


@pytest.mark.asyncio
async def test_bundle_404_when_video_missing(db_and_app):
    sessionmaker, app, _ = db_and_app
    clip_id = await _insert_clip(sessionmaker)  # video_path points at /tmp/missing.mp4
    r = TestClient(app).get(f"/v1/clips/{clip_id}/bundle.zip")
    assert r.status_code == 404


# ─── cover ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cover_served_with_right_mime(db_and_app):
    sessionmaker, app, tmp_path = db_and_app
    cover_png = tmp_path / "cov.png"
    cover_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    clip_id = await _insert_clip(sessionmaker, cover_path=cover_png)
    r = TestClient(app).get(f"/v1/clips/{clip_id}/cover")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content == cover_png.read_bytes()


@pytest.mark.asyncio
async def test_cover_404_when_not_generated(db_and_app):
    sessionmaker, app, _ = db_and_app
    clip_id = await _insert_clip(sessionmaker, cover_path=None)
    r = TestClient(app).get(f"/v1/clips/{clip_id}/cover")
    assert r.status_code == 404


# ─── summary ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_summary_groups_by_status(db_and_app):
    sessionmaker, app, _ = db_and_app
    await _insert_clip(sessionmaker, status="pending_review")
    await _insert_clip(sessionmaker, status="pending_review")
    await _insert_clip(sessionmaker, status="approved")

    r = TestClient(app).get("/v1/clips/queue/summary")
    body = r.json()
    assert body["total"] == 3
    assert body["counts"]["pending_review"] == 2
    assert body["counts"]["approved"] == 1
