"""Review model for clip quality feedback loop."""

import uuid
from datetime import datetime
from forge_engine.core.timeutils import utcnow

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from forge_engine.core.database import Base


class ClipReview(Base):
    """Review of an exported clip - feeds back into ML scoring.

    This is the core of the retroactive quality loop:
    1. User reviews exported clips (rating + tags)
    2. Reviews are collected as training data
    3. ML scoring model is periodically retrained
    4. Future scoring improves based on human feedback
    """

    __tablename__ = "clip_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Link to exported clip
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Rating (1-5 stars)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5

    # Quality tags (multi-select feedback)
    quality_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Possible tags: "good_hook", "bad_hook", "funny", "boring", "good_timing",
    # "bad_timing", "good_captions", "bad_captions", "good_framing", "bad_framing",
    # "publishable", "needs_edit", "skip"

    # Issue tags for specific problems
    issue_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Possible issues: "subtitle_desync", "bad_crop", "audio_issue", "too_long",
    # "too_short", "missing_context", "cut_too_early", "cut_too_late"

    # Free-form notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Publication decision
    publish_decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "approve", "reject", "edit_needed", "maybe"

    # Platform performance (filled after publication)
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Scoring comparison
    predicted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    human_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # rating * 20 (1-5 -> 20-100)
    score_delta: Mapped[float | None] = mapped_column(Float, nullable=True)  # predicted - human

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "segmentId": self.segment_id,
            "artifactId": self.artifact_id,
            "rating": self.rating,
            "qualityTags": self.quality_tags or [],
            "issueTags": self.issue_tags or [],
            "notes": self.notes,
            "publishDecision": self.publish_decision,
            "platform": self.platform,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "predictedScore": self.predicted_score,
            "humanScore": self.human_score,
            "scoreDelta": self.score_delta,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


class ClipQueue(Base):
    """Queue of clips pending review / publication.

    Generated automatically by the auto-pipeline.
    Status flow: pending_review -> approved/rejected -> scheduled -> published
    """

    __tablename__ = "clip_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Source
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Clip metadata
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Video file
    video_path: Mapped[str] = mapped_column(Text, nullable=False)
    cover_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0)

    # Score
    viral_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    # pending_review, approved, rejected, scheduled, published, failed

    # Publication
    target_platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publish_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Channel
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Review link
    review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utcnow,
        onupdate=utcnow
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "segmentId": self.segment_id,
            "artifactId": self.artifact_id,
            "title": self.title,
            "description": self.description,
            "hashtags": self.hashtags or [],
            "videoPath": self.video_path,
            "coverPath": self.cover_path,
            "duration": self.duration,
            "viralScore": self.viral_score,
            "status": self.status,
            "targetPlatform": self.target_platform,
            "scheduledAt": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "publishedUrl": self.published_url,
            "publishError": self.publish_error,
            "channelName": self.channel_name,
            "reviewId": self.review_id,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }
