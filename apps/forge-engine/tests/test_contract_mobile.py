"""Contract tests for the mobile (iOS) clip surface.

These lock the *backend* end of the desktop↔backend↔iOS contract:
  • ``ClipQueue.to_dict()`` emits exactly the documented camelCase keys.
  • The committed fixture (single source of truth, also validated by the zod and
    Swift suites) stays in sync with what the backend actually serializes.
  • Every field the iOS ``Clip`` struct decodes is present in the payload.

If a backend change adds/removes/renames a key, this fails — forcing the shared
schema, the iOS model, and the fixture to be updated together.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from forge_engine.models.review import ClipQueue

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "shared"
    / "contract"
    / "mobile-clip.sample.json"
)

# The full camelCase contract emitted by ClipQueue.to_dict().
EXPECTED_CLIP_KEYS = {
    "id",
    "projectId",
    "segmentId",
    "artifactId",
    "title",
    "description",
    "hashtags",
    "videoPath",
    "coverPath",
    "duration",
    "viralScore",
    "status",
    "targetPlatform",
    "scheduledAt",
    "publishedAt",
    "publishedUrl",
    "publishError",
    "channelName",
    "reviewId",
    "createdAt",
    "updatedAt",
}

# The subset the iOS `Clip` struct (apps/ios/ForgeLab/Models/Clip.swift) decodes.
IOS_REQUIRED_KEYS = {
    "id",
    "projectId",
    "segmentId",
    "title",
    "description",
    "hashtags",
    "coverPath",
    "duration",
    "viralScore",
    "status",
    "channelName",
    "createdAt",
}


def _sample_clip() -> ClipQueue:
    clip = ClipQueue(
        id="a1b2c3d4-0000-4000-8000-000000000001",
        project_id="b2c3d4e5-0000-4000-8000-000000000002",
        segment_id="c3d4e5f6-0000-4000-8000-000000000003",
        title="clip",
        description="desc",
        hashtags=["a", "b"],
        video_path="v.mp4",
        cover_path="c.jpg",
        duration=34.0,
        viral_score=92.0,
        status="pending_review",
        channel_name="etostark",
    )
    clip.created_at = datetime(2026, 6, 14, 8, 30, 0, 123456)
    clip.updated_at = datetime(2026, 6, 14, 8, 30, 0, 123456)
    return clip


def test_to_dict_emits_exact_contract_keys():
    keys = set(_sample_clip().to_dict().keys())
    assert keys == EXPECTED_CLIP_KEYS, (
        "ClipQueue.to_dict() drifted from the documented mobile contract. "
        "Update mobile.ts (zod), Clip.swift, the fixture, and EXPECTED_CLIP_KEYS "
        "together.\n"
        f"  added:   {keys - EXPECTED_CLIP_KEYS}\n"
        f"  removed: {EXPECTED_CLIP_KEYS - keys}"
    )


def test_ios_required_keys_present_and_typed():
    d = _sample_clip().to_dict()
    assert IOS_REQUIRED_KEYS <= set(d.keys())
    # Types the Swift decoder is strict about.
    assert isinstance(d["id"], str)
    assert isinstance(d["hashtags"], list)
    assert isinstance(d["duration"], (int, float))
    assert isinstance(d["viralScore"], (int, float))
    assert isinstance(d["createdAt"], str)


def test_fixture_exists():
    assert FIXTURE_PATH.exists(), (
        f"Missing contract fixture at {FIXTURE_PATH}. "
        "Regenerate with scripts/gen_contract_fixture.py"
    )


def test_fixture_clip_matches_backend_keys():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert set(fixture["clip"].keys()) == EXPECTED_CLIP_KEYS, (
        "Fixture is stale — regenerate with scripts/gen_contract_fixture.py"
    )


def test_fixture_response_envelopes_shape():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    by_date = fixture["clipsByDateResponse"]
    assert set(by_date.keys()) == {"date", "count", "items"}
    assert by_date["count"] == len(by_date["items"])

    resp = fixture["batchApproveResponse"]
    assert set(resp.keys()) == {"requested", "approved", "skipped"}

    summary = fixture["queueSummaryResponse"]
    assert set(summary.keys()) == {"counts", "total"}
    assert summary["total"] == sum(summary["counts"].values())


def test_datetime_serialization_is_iso_naive():
    # Documents the exact format the zod/Swift sides must accept: ISO-8601 with
    # microseconds and NO timezone suffix.
    created = _sample_clip().to_dict()["createdAt"]
    assert created == "2026-06-14T08:30:00.123456"
    # Round-trips through datetime.fromisoformat.
    assert datetime.fromisoformat(created) == datetime(2026, 6, 14, 8, 30, 0, 123456)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
