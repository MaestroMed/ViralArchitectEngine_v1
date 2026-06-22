"""Clip Review & Quality Feedback API endpoints.

Handles the retroactive quality loop:
- Review exported clips with ratings and tags
- Feed reviews into ML scoring model
- Track prediction accuracy over time
- Manage the clip publication queue
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from forge_engine.core.database import async_session_maker, get_db
from forge_engine.core.jobs import JobManager, JobType
from forge_engine.models.review import ClipQueue, ClipReview
from forge_engine.models.segment import Segment
from forge_engine.services.captions import CAPTION_PRESETS
from forge_engine.services.export import ExportService

router = APIRouter()


# ================================================================
# Request / Response Models
# ================================================================

class CreateReviewRequest(BaseModel):
    """Submit a review for an exported clip."""
    segment_id: str
    project_id: str
    artifact_id: str | None = None
    rating: int = Field(..., ge=1, le=5, description="1-5 stars")
    quality_tags: list[str] | None = None
    issue_tags: list[str] | None = None
    notes: str | None = None
    publish_decision: str | None = None  # approve, reject, edit_needed, maybe


class UpdateReviewRequest(BaseModel):
    """Update an existing review."""
    rating: int | None = Field(None, ge=1, le=5)
    quality_tags: list[str] | None = None
    issue_tags: list[str] | None = None
    notes: str | None = None
    publish_decision: str | None = None


class UpdatePerformanceRequest(BaseModel):
    """Update clip performance data after publication."""
    platform: str
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None


class QueueClipRequest(BaseModel):
    """Add a clip to the publication queue."""
    segment_id: str
    project_id: str
    artifact_id: str | None = None
    video_path: str
    cover_path: str | None = None
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    target_platform: str | None = "youtube"
    channel_name: str | None = "EtoStark"


class ApproveClipRequest(BaseModel):
    """Approve a clip for publication."""
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    target_platform: str | None = None
    scheduled_at: str | None = None  # ISO datetime


# ================================================================
# Review endpoints
# ================================================================

@router.post("/reviews")
async def create_review(
    request: CreateReviewRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Submit a review for an exported clip.

    This feeds into the ML scoring model to improve future predictions.
    """
    # Get segment to compare scores
    segment_result = await db.execute(
        select(Segment).where(Segment.id == request.segment_id)
    )
    segment = segment_result.scalar_one_or_none()

    predicted_score = segment.score_total if segment else None
    human_score = request.rating * 20.0  # 1-5 -> 20-100
    score_delta = (predicted_score - human_score) if predicted_score else None

    review = ClipReview(
        project_id=request.project_id,
        segment_id=request.segment_id,
        artifact_id=request.artifact_id,
        rating=request.rating,
        quality_tags=request.quality_tags,
        issue_tags=request.issue_tags,
        notes=request.notes,
        publish_decision=request.publish_decision,
        predicted_score=predicted_score,
        human_score=human_score,
        score_delta=score_delta,
    )

    db.add(review)
    await db.flush()

    # Feed into ML scoring model
    try:
        from forge_engine.services.ml_scoring import MLScoringService
        ml_service = MLScoringService.get_instance()

        if segment:
            segment_dict = {
                "id": segment.id,
                "project_id": segment.project_id,
                "duration": segment.duration,
                "transcript": segment.transcript or "",
                "start_time": segment.start_time,
                "score": {
                    "total": segment.score_total,
                    "hook_strength": segment.score_hook,
                },
            }
            ml_service.add_feedback(
                segment=segment_dict,
                rating=float(request.rating) * 2,  # 1-5 -> 2-10 scale for add_feedback
            )
    except Exception as e:
        # Don't fail the review if ML feedback fails
        import logging
        logging.getLogger(__name__).warning(f"ML feedback failed: {e}")

    return {
        "success": True,
        "data": review.to_dict(),
        "scoreDelta": score_delta,
    }


@router.get("/reviews")
async def list_reviews(
    project_id: str | None = None,
    segment_id: str | None = None,
    min_rating: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List reviews with optional filters."""
    query = select(ClipReview)
    count_query = select(func.count()).select_from(ClipReview)

    if project_id:
        query = query.where(ClipReview.project_id == project_id)
        count_query = count_query.where(ClipReview.project_id == project_id)
    if segment_id:
        query = query.where(ClipReview.segment_id == segment_id)
        count_query = count_query.where(ClipReview.segment_id == segment_id)
    if min_rating:
        query = query.where(ClipReview.rating >= min_rating)
        count_query = count_query.where(ClipReview.rating >= min_rating)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(ClipReview.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    reviews = result.scalars().all()

    return {
        "success": True,
        "data": {
            "items": [r.to_dict() for r in reviews],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    }


@router.get("/reviews/{review_id}")
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a specific review."""
    result = await db.execute(
        select(ClipReview).where(ClipReview.id == review_id)
    )
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return {"success": True, "data": review.to_dict()}


@router.patch("/reviews/{review_id}")
async def update_review(
    review_id: str,
    request: UpdateReviewRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update an existing review."""
    result = await db.execute(
        select(ClipReview).where(ClipReview.id == review_id)
    )
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if request.rating is not None:
        review.rating = request.rating
        review.human_score = request.rating * 20.0
        if review.predicted_score:
            review.score_delta = review.predicted_score - review.human_score
    if request.quality_tags is not None:
        review.quality_tags = request.quality_tags
    if request.issue_tags is not None:
        review.issue_tags = request.issue_tags
    if request.notes is not None:
        review.notes = request.notes
    if request.publish_decision is not None:
        review.publish_decision = request.publish_decision

    return {"success": True, "data": review.to_dict()}


@router.post("/reviews/{review_id}/performance")
async def update_performance(
    review_id: str,
    request: UpdatePerformanceRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update clip performance data after publication."""
    result = await db.execute(
        select(ClipReview).where(ClipReview.id == review_id)
    )
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.platform = request.platform
    if request.views is not None:
        review.views = request.views
    if request.likes is not None:
        review.likes = request.likes
    if request.comments is not None:
        review.comments = request.comments
    if request.shares is not None:
        review.shares = request.shares

    return {"success": True, "data": review.to_dict()}


# ================================================================
# ML Feedback & Training endpoints
# ================================================================

@router.get("/ml/status")
async def get_ml_status() -> dict:
    """Get ML scoring model status and accuracy metrics."""
    from forge_engine.services.ml_scoring import MLScoringService

    ml_service = MLScoringService.get_instance()

    return {
        "available": ml_service.is_available(),
        "modelTrained": ml_service.is_model_trained(),
        "modelInfo": ml_service.get_model_info(),
        "trainingDataCount": ml_service.get_training_data_count(),
        "canTrain": ml_service.can_train(),
        "minTrainingExamples": ml_service.MIN_TRAINING_EXAMPLES,
    }


@router.post("/ml/train")
async def train_ml_model(
    force: bool = False
) -> dict:
    """Trigger ML model training with collected reviews."""
    from forge_engine.services.ml_scoring import MLScoringService

    ml_service = MLScoringService.get_instance()

    if not ml_service.is_available():
        raise HTTPException(status_code=400, detail="scikit-learn not available")

    if not force and not ml_service.can_train():
        raise HTTPException(
            status_code=400,
            detail=f"Not enough training data: {ml_service.get_training_data_count()} / {ml_service.MIN_TRAINING_EXAMPLES}"
        )

    metadata = await ml_service.train_model(force=force)

    if metadata is None:
        raise HTTPException(status_code=500, detail="Training failed")

    return {
        "success": True,
        "model": {
            "version": metadata.version,
            "trainingExamples": metadata.training_examples,
            "cvScore": metadata.cv_score,
            "trainedAt": metadata.trained_at,
        }
    }


@router.get("/ml/accuracy")
async def get_ml_accuracy(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get accuracy metrics by comparing predicted vs human scores."""
    result = await db.execute(
        select(ClipReview).where(
            and_(
                ClipReview.predicted_score.isnot(None),
                ClipReview.human_score.isnot(None),
            )
        )
    )
    reviews = result.scalars().all()

    if not reviews:
        return {
            "totalReviews": 0,
            "accuracy": None,
            "message": "No reviews with score comparisons yet"
        }

    deltas = [r.score_delta for r in reviews if r.score_delta is not None]
    abs_deltas = [abs(d) for d in deltas]

    avg_delta = sum(deltas) / len(deltas) if deltas else 0
    avg_abs_delta = sum(abs_deltas) / len(abs_deltas) if abs_deltas else 0

    # Categorize accuracy
    within_10 = sum(1 for d in abs_deltas if d <= 10)
    within_20 = sum(1 for d in abs_deltas if d <= 20)

    return {
        "totalReviews": len(reviews),
        "averageDelta": round(avg_delta, 1),
        "averageAbsDelta": round(avg_abs_delta, 1),
        "within10Points": within_10,
        "within20Points": within_20,
        "accuracyRate10": round(within_10 / len(deltas) * 100, 1) if deltas else 0,
        "accuracyRate20": round(within_20 / len(deltas) * 100, 1) if deltas else 0,
        "bias": "overestimates" if avg_delta > 5 else "underestimates" if avg_delta < -5 else "calibrated",
    }


# ================================================================
# Clip Queue endpoints (for mobile review app)
# ================================================================

@router.get("/queue")
async def list_queue(
    status: str | None = None,
    channel: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List clips in the queue, sorted by viral score."""
    query = select(ClipQueue)
    count_query = select(func.count()).select_from(ClipQueue)

    if status:
        query = query.where(ClipQueue.status == status)
        count_query = count_query.where(ClipQueue.status == status)
    if channel:
        query = query.where(ClipQueue.channel_name == channel)
        count_query = count_query.where(ClipQueue.channel_name == channel)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(ClipQueue.viral_score.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    clips = result.scalars().all()

    return {
        "success": True,
        "data": {
            "items": [c.to_dict() for c in clips],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    }


@router.get("/queue/pending")
async def list_pending_clips(
    channel: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List clips pending review (for mobile app feed)."""
    query = select(ClipQueue).where(ClipQueue.status == "pending_review")

    if channel:
        query = query.where(ClipQueue.channel_name == channel)

    query = query.order_by(ClipQueue.viral_score.desc())

    result = await db.execute(query)
    clips = result.scalars().all()

    return {
        "success": True,
        "data": [c.to_dict() for c in clips],
        "count": len(clips),
    }


@router.post("/queue/{clip_id}/approve")
async def approve_clip(
    clip_id: str,
    request: ApproveClipRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Approve a clip for publication."""
    result = await db.execute(
        select(ClipQueue).where(ClipQueue.id == clip_id)
    )
    clip = result.scalar_one_or_none()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip.status = "approved"
    if request.title:
        clip.title = request.title
    if request.description:
        clip.description = request.description
    if request.hashtags:
        clip.hashtags = request.hashtags
    if request.target_platform:
        clip.target_platform = request.target_platform
    if request.scheduled_at:
        clip.scheduled_at = datetime.fromisoformat(request.scheduled_at)
        clip.status = "scheduled"

    return {"success": True, "data": clip.to_dict()}


@router.post("/queue/{clip_id}/reject")
async def reject_clip(
    clip_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Reject a clip."""
    result = await db.execute(
        select(ClipQueue).where(ClipQueue.id == clip_id)
    )
    clip = result.scalar_one_or_none()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip.status = "rejected"

    return {"success": True, "data": clip.to_dict()}


@router.patch("/queue/{clip_id}")
async def update_queued_clip(
    clip_id: str,
    title: str | None = None,
    description: str | None = None,
    hashtags: list[str] | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Edit a queued clip's metadata before publication."""
    result = await db.execute(
        select(ClipQueue).where(ClipQueue.id == clip_id)
    )
    clip = result.scalar_one_or_none()

    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    if title is not None:
        clip.title = title
    if description is not None:
        clip.description = description
    if hashtags is not None:
        clip.hashtags = hashtags

    return {"success": True, "data": clip.to_dict()}


# ================================================================
# In-app editor — caption presets + re-render
# ================================================================

# Display spec per preset so the iOS picker renders a chip without hardcoding.
# `highlight` is display hex (not ASS); `pop` flags the animated word-pop.
_PRESET_SPECS = {
    "classic": {"label": "Classique", "highlight": "#FFD400", "pop": False},
    "hormozi": {"label": "Hormozi", "highlight": "#00FF66", "pop": True},
    "pop": {"label": "Pop", "highlight": "#33D9F2", "pop": True},
    "minimal": {"label": "Minimal", "highlight": "#FFFFFF", "pop": False},
    "neon": {"label": "Neon", "highlight": "#FF3DCB", "pop": True},
}


@router.get("/caption-presets")
async def list_caption_presets() -> dict:
    """The dynamic caption styles the editor can pick from."""
    presets = [
        {"id": key, **_PRESET_SPECS.get(key, {"label": key.title(), "highlight": "#FFD400", "pop": False})}
        for key in CAPTION_PRESETS
    ]
    return {"success": True, "data": {"presets": presets}}


class RerenderRequest(BaseModel):
    """Re-render an existing queued clip with editor tweaks (all optional)."""
    model_config = {"populate_by_name": True}

    caption_style: dict | None = Field(default=None, alias="captionStyle")
    clip_start_override: float | None = Field(default=None, alias="clipStart")
    clip_duration_override: float | None = Field(default=None, alias="clipDuration")
    intro_config: dict | None = Field(default=None, alias="intro")
    jump_cut_config: dict | None = Field(default=None, alias="jumpCut")


async def _rerender_clip_handler(job, *, clip_id: str, **export_kwargs):
    """Job handler: render the new clip, then update the SAME ClipQueue row
    (video/cover/duration + render_params) so the edit replaces it in place."""
    export_service = ExportService()
    result = await export_service.run_export(job=job, **export_kwargs)

    video_path, cover_path = "", ""
    for a in result.get("artifacts", []) or []:
        t = a.get("type") if isinstance(a, dict) else getattr(a, "type", None)
        p = a.get("path") if isinstance(a, dict) else getattr(a, "path", None)
        if t == "video":
            video_path = p or ""
        elif t == "cover":
            cover_path = p or ""
    if not video_path:
        ed = result.get("export_dir", "")
        if ed:
            mp4s = list(Path(ed).glob("*.mp4"))
            if mp4s:
                video_path = str(mp4s[0])

    async with async_session_maker() as db:
        clip = (await db.execute(select(ClipQueue).where(ClipQueue.id == clip_id))).scalar_one_or_none()
        if clip and video_path:
            clip.video_path = video_path
            if cover_path:
                clip.cover_path = cover_path
            dur = export_kwargs.get("clip_duration_override")
            if dur:
                clip.duration = dur
            rp = dict(clip.render_params or {})
            if export_kwargs.get("clip_start_override") is not None:
                rp["clipStart"] = export_kwargs["clip_start_override"]
            if dur:
                rp["clipDuration"] = dur
            cs = export_kwargs.get("caption_style") or {}
            if cs.get("presetId"):
                rp["presetId"] = cs["presetId"]
            clip.render_params = rp
            await db.commit()
    return result


@router.post("/queue/{clip_id}/rerender")
async def rerender_clip(
    clip_id: str,
    request: RerenderRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-render a queued clip with editor tweaks (caption style / trim / intro).

    Reuses the stored trim window (render_params) unless the request overrides it,
    so a pure restyle keeps the exact same moment. Returns the EXPORT job id; the
    client tracks it over the WS and the ClipQueue row updates in place on finish.
    """
    clip = (await db.execute(select(ClipQueue).where(ClipQueue.id == clip_id))).scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    segment = (await db.execute(select(Segment).where(Segment.id == clip.segment_id))).scalar_one_or_none()
    if not segment:
        raise HTTPException(status_code=404, detail="Source segment not found")

    rp = clip.render_params or {}
    start = request.clip_start_override
    if start is None:
        start = rp.get("clipStart", segment.start_time)
    duration = request.clip_duration_override
    if duration is None:
        duration = rp.get("clipDuration", clip.duration)

    caption_style = dict(request.caption_style or {})
    caption_style.setdefault("presetId", rp.get("presetId", "classic"))

    job_manager = JobManager.get_instance()
    job = await job_manager.create_job(
        job_type=JobType.EXPORT,
        handler=_rerender_clip_handler,
        clip_id=clip_id,
        project_id=clip.project_id,
        segment_id=clip.segment_id,
        variant="edit",
        platform=rp.get("platform", "tiktok"),
        include_captions=True,
        burn_subtitles=True,
        include_cover=True,
        use_nvenc=True,
        caption_style=caption_style,
        intro_config=request.intro_config,
        jump_cut_config=request.jump_cut_config,
        clip_start_override=start,
        clip_duration_override=duration,
    )
    return {"success": True, "data": {"jobId": job.id, "clipId": clip_id}}
