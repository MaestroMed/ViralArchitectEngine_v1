"""Regression tests for POST /v1/social/publish.

The route used to call ``service.publish(platform=..., video_path=..., ...)``
with keyword args, but ``SocialPublishService.publish`` takes a SINGLE
``PublishRequest`` dataclass positional and returns a ``PublishResult`` — so
every publish attempt raised ``TypeError`` before any upload could start (the
twin of the already-fixed status-route bug). These tests pin the contract: the
endpoint builds the dataclass (mapping ``visibility`` -> ``privacy``, parsing
the ISO ``schedule_time``), passes it positionally, and translates the result
into a ``"<platform>:<video_id>"`` token without a TypeError.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_engine.api.v1.endpoints import social
from forge_engine.services.credential_store import CredentialStore
from forge_engine.services.social_publish import (
    Platform,
    PublishRequest,
    PublishResult,
    PublishStatus,
    SocialPublishService,
)


@pytest.fixture
def service(tmp_path) -> SocialPublishService:
    return SocialPublishService(store=CredentialStore(path=tmp_path / "creds.enc"))


def _client(service) -> TestClient:
    app = FastAPI()
    app.include_router(social.router)
    return TestClient(app)


def test_publish_builds_dataclass_and_returns_token(service, monkeypatch):
    """The route must hand publish() a single PublishRequest dataclass (not
    kwargs) and translate the PublishResult back into a status token."""
    captured: dict = {}

    async def fake_publish(req, progress_callback=None):
        captured["req"] = req
        return PublishResult(
            success=True,
            platform=req.platform,
            status=PublishStatus.PROCESSING,
            video_id="vidABC",
            video_url="https://youtube.com/shorts/vidABC",
        )

    monkeypatch.setattr(service, "publish", fake_publish)
    monkeypatch.setattr(service, "get_connected_platforms", lambda: ["youtube"])
    monkeypatch.setattr(SocialPublishService, "_instance", service, raising=False)

    resp = _client(service).post(
        "/publish",
        json={
            "platform": "youtube",
            "video_path": "/x.mp4",
            "title": "T",
            "description": "D",
            "hashtags": ["a", "b"],
            "schedule_time": "2026-06-22T10:00:00",
            "visibility": "unlisted",
        },
    )

    assert resp.status_code == 200  # not 500 — the kwargs TypeError path is gone
    body = resp.json()
    assert body["job_id"] == "youtube:vidABC"
    assert body["platform"] == "youtube"
    assert body["status"] == "processing"
    assert body["url"] == "https://youtube.com/shorts/vidABC"

    # The service received a single PublishRequest DATACLASS, correctly mapped.
    req = captured["req"]
    assert isinstance(req, PublishRequest)
    assert req.platform == Platform.YOUTUBE
    assert req.privacy == "unlisted"  # visibility -> privacy
    assert req.schedule_time == datetime(2026, 6, 22, 10, 0, 0)  # ISO parsed
    assert req.hashtags == ["a", "b"]
    assert req.description == "D"


def test_publish_failure_surfaces_502(service, monkeypatch):
    """A stub/failed publisher returns success=False -> 502, not a 500."""

    async def failing_publish(req, progress_callback=None):
        return PublishResult(
            success=False,
            platform=req.platform,
            status=PublishStatus.FAILED,
            error="stub not implemented",
        )

    monkeypatch.setattr(service, "publish", failing_publish)
    monkeypatch.setattr(service, "get_connected_platforms", lambda: ["tiktok"])
    monkeypatch.setattr(SocialPublishService, "_instance", service, raising=False)

    resp = _client(service).post(
        "/publish", json={"platform": "tiktok", "video_path": "/x.mp4", "title": "T"}
    )
    assert resp.status_code == 502
    assert "stub" in resp.json()["detail"]


def test_publish_not_connected_400(service, monkeypatch):
    monkeypatch.setattr(service, "get_connected_platforms", lambda: [])
    monkeypatch.setattr(SocialPublishService, "_instance", service, raising=False)

    resp = _client(service).post(
        "/publish", json={"platform": "youtube", "video_path": "/x.mp4", "title": "T"}
    )
    assert resp.status_code == 400


def test_publish_bad_schedule_time_400(service, monkeypatch):
    monkeypatch.setattr(service, "get_connected_platforms", lambda: ["youtube"])
    monkeypatch.setattr(SocialPublishService, "_instance", service, raising=False)

    resp = _client(service).post(
        "/publish",
        json={
            "platform": "youtube",
            "video_path": "/x.mp4",
            "title": "T",
            "schedule_time": "not-a-date",
        },
    )
    assert resp.status_code == 400
