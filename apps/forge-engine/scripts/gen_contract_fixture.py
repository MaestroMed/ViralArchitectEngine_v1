"""Regenerate the cross-language mobile contract fixture.

The fixture (``packages/shared/contract/mobile-clip.sample.json``) is the single
source of truth validated by the Python, TypeScript (zod) and Swift contract
tests. It is generated from the *real* ``ClipQueue.to_dict()`` serializer so it
can never silently drift from the backend.

Usage (from apps/forge-engine):
    PYTHONPATH=src python scripts/gen_contract_fixture.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from forge_engine.models.review import ClipQueue

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "shared"
    / "contract"
    / "mobile-clip.sample.json"
)

_STAMP = datetime(2026, 6, 14, 8, 30, 0, 123456)


def build_fixture() -> dict:
    clip = ClipQueue(
        id="a1b2c3d4-0000-4000-8000-000000000001",
        project_id="b2c3d4e5-0000-4000-8000-000000000002",
        segment_id="c3d4e5f6-0000-4000-8000-000000000003",
        artifact_id="d4e5f6a7-0000-4000-8000-000000000004",
        title="\"Le outplay de Cabochard là c'est ILLÉGAL\"",
        description="KC vs G2, la diff top qui fait basculer la game",
        hashtags=["lol", "lec", "karminecorp", "etostark"],
        video_path="projects/b2c3d4e5/exports/clip_001_A.mp4",
        cover_path="projects/b2c3d4e5/exports/clip_001_A.jpg",
        duration=34.0,
        viral_score=92.0,
        status="pending_review",
        target_platform=None,
        channel_name="etostark",
        review_id=None,
    )
    # Python-side column defaults only fire on flush; set timestamps explicitly.
    clip.created_at = _STAMP
    clip.updated_at = _STAMP
    clip.scheduled_at = None
    clip.published_at = None
    clip.published_url = None
    clip.publish_error = None

    clip_dict = clip.to_dict()
    return {
        "_comment": (
            "Auto-generated from ClipQueue.to_dict() — DO NOT hand-edit. "
            "Regenerate via apps/forge-engine/scripts/gen_contract_fixture.py. "
            "Single source of truth for the desktop<->backend<->iOS contract."
        ),
        "clip": clip_dict,
        "clipsByDateResponse": {
            "date": "2026-06-14",
            "count": 1,
            "items": [clip_dict],
        },
        "batchApproveRequest": {
            "ids": [clip_dict["id"], "e5f6a7b8-0000-4000-8000-000000000005"],
        },
        "batchApproveResponse": {
            "requested": 2,
            "approved": 1,
            "skipped": ["e5f6a7b8-0000-4000-8000-000000000005"],
        },
        "queueSummaryResponse": {
            "counts": {"pending_review": 4, "approved": 1, "published": 12},
            "total": 17,
        },
        "health": {"status": "healthy", "version": "1.0.0"},
    }


def main() -> None:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(build_fixture(), f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {FIXTURE_PATH}")


if __name__ == "__main__":
    main()
