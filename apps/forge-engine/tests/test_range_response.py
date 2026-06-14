"""Range-request streamer tests — the iPhone preview is built on these."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from forge_engine.core.range_response import _parse_range, serve_file_with_range

PAYLOAD = b"".join(bytes([i % 256]) for i in range(8 * 1024))  # 8 KiB of varied bytes


@pytest.fixture
def video(tmp_path: Path) -> Path:
    p = tmp_path / "clip.mp4"
    p.write_bytes(PAYLOAD)
    return p


@pytest.fixture
def app(video: Path) -> FastAPI:
    app = FastAPI()

    @app.get("/video")
    async def stream(request: Request):
        return serve_file_with_range(request, video, media_type="video/mp4")

    return app


# ─── Parse-only tests (pure logic) ────────────────────────────────────────────

@pytest.mark.parametrize(
    ("header", "size", "expected"),
    [
        ("bytes=0-1023", 8192, (0, 1023)),
        ("bytes=1024-", 8192, (1024, 8191)),
        ("bytes=-500", 8192, (7692, 8191)),
        ("bytes=0-0", 8192, (0, 0)),  # single byte
        ("bytes=0-8191", 8192, (0, 8191)),  # entire file
    ],
)
def test_parse_range_valid(header, size, expected):
    assert _parse_range(header, size) == expected


@pytest.mark.parametrize(
    "header",
    [
        "items=0-100",     # wrong unit
        "bytes=-",         # empty suffix
        "bytes=100-50",    # inverted
        "bytes=0-9999",    # past EOF
        "bytes=9000-",     # start past EOF
        "bytes=abc-100",   # non-numeric
    ],
)
def test_parse_range_invalid(header):
    assert _parse_range(header, 8192) is None


# ─── HTTP integration tests ───────────────────────────────────────────────────

def test_no_range_returns_full_file(app):
    client = TestClient(app)
    r = client.get("/video")
    assert r.status_code == 200
    assert r.content == PAYLOAD
    assert r.headers["accept-ranges"] == "bytes"
    assert int(r.headers["content-length"]) == len(PAYLOAD)


def test_first_range(app):
    client = TestClient(app)
    r = client.get("/video", headers={"Range": "bytes=0-1023"})
    assert r.status_code == 206
    assert r.content == PAYLOAD[:1024]
    assert r.headers["content-range"] == f"bytes 0-1023/{len(PAYLOAD)}"
    assert int(r.headers["content-length"]) == 1024


def test_open_ended_range(app):
    client = TestClient(app)
    r = client.get("/video", headers={"Range": "bytes=4096-"})
    assert r.status_code == 206
    assert r.content == PAYLOAD[4096:]
    assert r.headers["content-range"] == f"bytes 4096-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"


def test_suffix_range(app):
    client = TestClient(app)
    r = client.get("/video", headers={"Range": "bytes=-500"})
    assert r.status_code == 206
    assert r.content == PAYLOAD[-500:]


def test_malformed_range_returns_416(app):
    client = TestClient(app)
    r = client.get("/video", headers={"Range": "bytes=100-50"})
    assert r.status_code == 416
    assert r.headers["content-range"] == f"bytes */{len(PAYLOAD)}"


def test_case_insensitive_header(app):
    """HTTP headers are case-insensitive; nginx and some iOS clients lowercase."""
    client = TestClient(app)
    r = client.get("/video", headers={"range": "bytes=0-9"})
    assert r.status_code == 206
    assert len(r.content) == 10


def test_missing_file_returns_404(tmp_path):
    missing = tmp_path / "nope.mp4"
    app = FastAPI()

    @app.get("/v")
    async def s(request: Request):
        return serve_file_with_range(request, missing, media_type="video/mp4")

    r = TestClient(app).get("/v")
    assert r.status_code == 404
