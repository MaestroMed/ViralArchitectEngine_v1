"""Regression tests for the /v1/social/publish/{id} status flow.

The `get_publish_status` alias used to forward its single `job_id` argument
straight to `get_publishing_status(platform, video_id)`, so `job_id` landed in
the `platform` slot and `video_id` was missing — every call to the endpoint
raised `TypeError` at runtime. These tests pin the contract: the alias decodes
a `"<platform>:<video_id>"` token, calls the primitive with the right args, and
returns a payload the endpoint can serialize without a TypeError.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_engine.api.v1.endpoints import social
from forge_engine.services.credential_store import CredentialStore
from forge_engine.services.social_publish import Platform, SocialPublishService

YOUTUBE_PAYLOAD = {
    "id": "vid123",
    "status": {"uploadStatus": "processed", "privacyStatus": "public"},
}


@pytest.fixture
def service(tmp_path) -> SocialPublishService:
    """A service backed by an empty, throwaway credential store (no real I/O)."""
    return SocialPublishService(store=CredentialStore(path=tmp_path / "creds.enc"))


# ── Unit: the alias itself ────────────────────────────────────────────────────


async def test_alias_passes_platform_and_video_id(service, monkeypatch):
    """The alias must call the primitive with (platform, video_id) — not a
    single positional `job_id` (the original TypeError)."""
    captured: dict = {}

    async def fake_status(platform, video_id):
        captured["platform"] = platform
        captured["video_id"] = video_id
        return YOUTUBE_PAYLOAD

    monkeypatch.setattr(service, "get_publishing_status", fake_status)

    result = await service.get_publish_status("youtube:vid123")

    assert captured == {"platform": Platform.YOUTUBE, "video_id": "vid123"}
    assert result == {
        "job_id": "youtube:vid123",
        "platform": "youtube",
        "status": "processed",
        "url": "https://youtube.com/shorts/vid123",
        "error": None,
    }


async def test_alias_surfaces_failure_reason(service, monkeypatch):
    async def fake_status(platform, video_id):
        return {"status": {"uploadStatus": "failed", "failureReason": "codec"}}

    monkeypatch.setattr(service, "get_publishing_status", fake_status)

    result = await service.get_publish_status("youtube:vid123")

    assert result["status"] == "failed"
    assert result["error"] == "codec"


@pytest.mark.parametrize("job_id", ["", "vid-only", "novideo:", "bogus:vid123"])
async def test_alias_returns_none_for_unresolvable_tokens(service, monkeypatch, job_id):
    """Malformed token or unknown platform → None (404), never a TypeError."""

    async def fake_status(platform, video_id):  # pragma: no cover - shouldn't run
        return YOUTUBE_PAYLOAD

    monkeypatch.setattr(service, "get_publishing_status", fake_status)

    assert await service.get_publish_status(job_id) is None


async def test_alias_returns_none_when_primitive_has_nothing(service, monkeypatch):
    async def fake_status(platform, video_id):
        return None

    monkeypatch.setattr(service, "get_publishing_status", fake_status)

    assert await service.get_publish_status("youtube:vid123") is None


# ── End-to-end: through the FastAPI route that triggered the bug ───────────────


@pytest.fixture
def client(service, monkeypatch):
    """TestClient over the real social router, wired to our throwaway service."""

    async def fake_status(platform, video_id):
        if video_id == "vid123":
            return YOUTUBE_PAYLOAD
        return None

    # Real alias under test; only the network-touching primitive is stubbed.
    monkeypatch.setattr(service, "get_publishing_status", fake_status)
    monkeypatch.setattr(SocialPublishService, "_instance", service, raising=False)

    app = FastAPI()
    app.include_router(social.router)
    return TestClient(app)


def test_endpoint_returns_status_without_typeerror(client):
    resp = client.get("/publish/youtube:vid123")

    assert resp.status_code == 200  # not 500 — the TypeError path is gone
    body = resp.json()
    assert body["job_id"] == "youtube:vid123"
    assert body["platform"] == "youtube"
    assert body["status"] == "processed"
    assert body["url"] == "https://youtube.com/shorts/vid123"


def test_endpoint_404_for_unknown_job(client):
    resp = client.get("/publish/youtube:does-not-exist")
    assert resp.status_code == 404
