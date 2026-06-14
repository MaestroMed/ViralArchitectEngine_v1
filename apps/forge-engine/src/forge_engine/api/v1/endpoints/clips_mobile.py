"""Mobile-shaped clip endpoints — the routes the iPhone app actually needs.

These live alongside the existing /v1/clips queue routes (see `reviews.py`).
Splitting them keeps the older review.py file focused on the desktop review
workflow and avoids accidental regressions there.

Routes:
- GET    /v1/clips/by-date?date=YYYY-MM-DD   list the queue for a given day
- POST   /v1/clips/batch-approve             approve N clips atomically
- GET    /v1/clips/{id}/bundle.zip           streamed ZIP: clip + cover + meta
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, func, select, update

from forge_engine.core.database import async_session_maker
from forge_engine.models.review import ClipQueue

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── GET /by-date ────────────────────────────────────────────────────────────

class ClipsByDateResponse(BaseModel):
    date: str
    count: int
    items: list[dict]


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date {value!r}, expected YYYY-MM-DD") from exc


@router.get("/by-date")
async def list_clips_by_date(
    date_str: Annotated[str, Query(alias="date", description="YYYY-MM-DD")],
    channel: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> ClipsByDateResponse:
    """Return every clip whose ``created_at`` falls on the given local-ish day.

    The "morning workflow" is: open the phone, see yesterday's clips. We
    interpret the date in UTC (DB stores naive UTC timestamps) — the iPhone
    app can pass either today or yesterday depending on the user's TZ. A
    half-open [day, day+1) range avoids the late-night-clip edge case where
    a strict equality misses 23:59:xx entries.
    """
    target = _parse_iso_date(date_str)
    start = datetime.combine(target, time.min)
    end = start + timedelta(days=1)

    filters = [ClipQueue.created_at >= start, ClipQueue.created_at < end]
    if channel:
        filters.append(ClipQueue.channel_name == channel)
    if status_filter:
        filters.append(ClipQueue.status == status_filter)

    async with async_session_maker() as db:
        result = await db.execute(
            select(ClipQueue)
            .where(and_(*filters))
            .order_by(ClipQueue.viral_score.desc(), ClipQueue.created_at.desc())
        )
        clips = result.scalars().all()

    return ClipsByDateResponse(
        date=target.isoformat(),
        count=len(clips),
        items=[c.to_dict() for c in clips],
    )


# ─── POST /batch-approve ─────────────────────────────────────────────────────

class BatchApproveRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, max_length=100)

    @field_validator("ids")
    @classmethod
    def _no_blanks(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("ids must contain at least one non-empty string")
        return cleaned


class BatchApproveResponse(BaseModel):
    requested: int
    approved: int
    skipped: list[str]


@router.post("/batch-approve")
async def batch_approve(request: BatchApproveRequest) -> BatchApproveResponse:
    """Approve a set of clips in a single transaction.

    Only clips currently in ``pending_review`` flip to ``approved``; anything
    else (already approved, rejected, published, missing) is reported in
    ``skipped`` so the client can show which ones didn't move.
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(ClipQueue.id, ClipQueue.status).where(ClipQueue.id.in_(request.ids))
        )
        rows = {row.id: row.status for row in result.all()}

        eligible = [i for i, st in rows.items() if st == "pending_review"]
        skipped = [i for i in request.ids if i not in eligible]

        if eligible:
            await db.execute(
                update(ClipQueue)
                .where(ClipQueue.id.in_(eligible))
                .values(status="approved", updated_at=datetime.utcnow())
            )
            await db.commit()

    return BatchApproveResponse(
        requested=len(request.ids),
        approved=len(eligible),
        skipped=skipped,
    )


# ─── GET /{id}/bundle.zip ────────────────────────────────────────────────────

def _load_metadata(clip: ClipQueue) -> dict:
    """Compact JSON the iPhone app can drop into the system clipboard as the
    TikTok caption (title + hashtags joined). Keeps everything self-contained
    so the user doesn't need to re-query the server while offline."""
    return {
        "id": clip.id,
        "title": clip.title,
        "description": clip.description,
        "hashtags": clip.hashtags or [],
        "duration": clip.duration,
        "viralScore": clip.viral_score,
        "channelName": clip.channel_name,
        "createdAt": clip.created_at.isoformat(),
        # Pre-built TikTok caption: caller can copy this straight to clipboard.
        "caption": _build_caption(clip.title, clip.description, clip.hashtags or []),
    }


def _build_caption(title: str | None, description: str | None, hashtags: list[str]) -> str:
    """Concatenate fields the way a creator usually formats them."""
    parts: list[str] = []
    if title:
        parts.append(title.strip())
    if description and description.strip() != (title or "").strip():
        parts.append(description.strip())
    if hashtags:
        # Always prefix hashtags with '#' — auto_pipeline sometimes stores them stripped.
        tags = [(t if t.startswith("#") else f"#{t}") for t in hashtags if t]
        parts.append(" ".join(tags))
    return "\n\n".join(parts)


@router.get("/{clip_id}/bundle.zip")
async def clip_bundle(clip_id: str) -> StreamingResponse:
    """Stream a ZIP with the clip's video, cover, and metadata as a single
    file. The iPhone app downloads this once and stores the .mp4 to Photos
    and the caption to the clipboard."""
    async with async_session_maker() as db:
        result = await db.execute(select(ClipQueue).where(ClipQueue.id == clip_id))
        clip = result.scalar_one_or_none()
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")

    video = Path(clip.video_path)
    if not video.exists():
        raise HTTPException(status_code=404, detail="Video file missing on disk")
    cover = Path(clip.cover_path) if clip.cover_path else None

    # ZIP is built in-memory — clip bundles are <50 MB in practice, no need
    # for the complexity of a generator that opens the file twice.
    # Use ZIP_STORED on purpose: the .mp4 is already H.264-compressed, so
    # deflate adds CPU + a tiny size win. STORED also keeps the iOS reader
    # trivial (no need to depend on Compression.framework's deflate, which
    # is awkward for raw DEFLATE streams). See apps/ios/ForgeLab/Services/
    # ZipReader.swift for the matching consumer.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        zf.write(video, arcname="clip.mp4")
        if cover and cover.exists():
            zf.write(cover, arcname=f"cover{cover.suffix.lower() or '.jpg'}")
        zf.writestr("metadata.json", json.dumps(_load_metadata(clip), ensure_ascii=False, indent=2))
    buf.seek(0)
    filename = f"forge-clip-{clip.id[:8]}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── GET /{id}/cover ─────────────────────────────────────────────────────────

@router.get("/{clip_id}/cover")
async def clip_cover(clip_id: str) -> Response:
    """Serve the clip cover image, for the iPhone list thumbnails."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(ClipQueue.cover_path).where(ClipQueue.id == clip_id)
        )
        row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    cover_path = row[0]
    if not cover_path:
        raise HTTPException(status_code=404, detail="Cover not generated for this clip")
    path = Path(cover_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Cover file missing on disk")

    media = "image/jpeg"
    suffix = path.suffix.lower()
    if suffix in (".png",):
        media = "image/png"
    elif suffix in (".webp",):
        media = "image/webp"
    return Response(
        content=path.read_bytes(),
        media_type=media,
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ─── Stats helper for the dashboard (used by the iOS Home screen) ────────────

@router.get("/queue/summary")
async def queue_summary(
    channel: Annotated[str | None, Query()] = None,
) -> dict:
    """Counts by status — drives the iOS home badge."""
    filters = []
    if channel:
        filters.append(ClipQueue.channel_name == channel)
    async with async_session_maker() as db:
        stmt = select(ClipQueue.status, func.count()).group_by(ClipQueue.status)
        if filters:
            stmt = stmt.where(and_(*filters))
        result = await db.execute(stmt)
        counts = dict(result.all())
    return {"counts": counts, "total": sum(counts.values())}
