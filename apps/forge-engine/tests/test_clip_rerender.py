"""Editor backend — caption-presets endpoint + rerender contract.

Pins that POST /v1/clips/queue/{id}/rerender reuses the stored trim window
(render_params) and forwards the chosen preset into the export job, without
actually rendering (the JobManager is faked).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from forge_engine.api.v1.endpoints import reviews
from forge_engine.core.database import get_db
from forge_engine.models.project import Project
from forge_engine.models.review import ClipQueue
from forge_engine.models.segment import Segment


@pytest_asyncio.fixture
async def app_db(monkeypatch, tmp_path) -> AsyncIterator[tuple]:
    from forge_engine.core import database as db_module
    from forge_engine.models import (  # noqa: F401 — register all tables
        api_key, artifact, channel, device_token, job, profile, project,
        review, segment, template, training_data,
    )

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ed.db'}", future=True)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "async_session_maker", sm)
    monkeypatch.setattr(reviews, "async_session_maker", sm)
    async with engine.begin() as conn:
        await conn.run_sync(db_module.Base.metadata.create_all)

    async def _get_db():
        async with sm() as s:
            yield s

    app = FastAPI()
    app.dependency_overrides[get_db] = _get_db
    app.include_router(reviews.router, prefix="/v1/clips")
    yield sm, app
    await engine.dispose()


async def test_caption_presets_endpoint(app_db):
    _, app = app_db
    r = TestClient(app).get("/v1/clips/caption-presets")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["data"]["presets"]}
    assert {"classic", "hormozi", "pop", "minimal", "neon"} <= ids
    # each carries a display spec for the picker chip
    assert all("highlight" in p and "label" in p for p in r.json()["data"]["presets"])


async def test_rerender_reuses_window_and_forwards_preset(app_db, monkeypatch):
    sm, app = app_db
    async with sm() as db:
        db.add(Project(id="p1", name="t", source_path="/tmp/s.mp4", source_filename="s.mp4", status="ready"))
        db.add(Segment(id="seg-1", project_id="p1", start_time=100.0, end_time=300.0, duration=200.0, score_total=70.0))
        db.add(ClipQueue(
            id="clip-1", project_id="p1", segment_id="seg-1", video_path="/tmp/c.mp4", duration=60.0,
            render_params={"clipStart": 120.0, "clipDuration": 58.0, "presetId": "classic", "platform": "tiktok"},
        ))
        await db.commit()

    captured: dict = {}

    class FakeJob:
        id = "job-xyz"

    class FakeMgr:
        async def create_job(self, **kw):
            captured.update(kw)
            return FakeJob()

    monkeypatch.setattr(reviews.JobManager, "get_instance", classmethod(lambda cls: FakeMgr()))

    r = TestClient(app).post("/v1/clips/queue/clip-1/rerender", json={"captionStyle": {"presetId": "hormozi"}})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["jobId"] == "job-xyz"
    # preset forwarded; trim window reused from render_params (a pure restyle).
    assert captured["caption_style"]["presetId"] == "hormozi"
    assert captured["clip_start_override"] == 120.0
    assert captured["clip_duration_override"] == 58.0


async def test_rerender_clip_relative_trim_maps_onto_window(app_db, monkeypatch):
    sm, app = app_db
    async with sm() as db:
        db.add(Project(id="p1", name="t", source_path="/tmp/s.mp4", source_filename="s.mp4", status="ready"))
        db.add(Segment(id="seg-1", project_id="p1", start_time=100.0, end_time=300.0, duration=200.0, score_total=70.0))
        db.add(ClipQueue(
            id="clip-1", project_id="p1", segment_id="seg-1", video_path="/tmp/c.mp4", duration=58.0,
            render_params={"clipStart": 120.0, "clipDuration": 58.0, "presetId": "classic"},
        ))
        await db.commit()

    captured: dict = {}

    class FakeJob:
        id = "j1"

    class FakeMgr:
        async def create_job(self, **kw):
            captured.update(kw)
            return FakeJob()

    monkeypatch.setattr(reviews.JobManager, "get_instance", classmethod(lambda cls: FakeMgr()))
    # Trim to [5s, 30s) of the current clip → absolute start 125, duration 25.
    r = TestClient(app).post("/v1/clips/queue/clip-1/rerender", json={"trimIn": 5, "trimOut": 30})
    assert r.status_code == 200, r.text
    assert captured["clip_start_override"] == 125.0
    assert captured["clip_duration_override"] == 25.0


async def test_rerender_unknown_clip_404(app_db):
    _, app = app_db
    r = TestClient(app).post("/v1/clips/queue/nope/rerender", json={})
    assert r.status_code == 404
