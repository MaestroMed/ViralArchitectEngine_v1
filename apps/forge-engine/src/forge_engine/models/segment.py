"""Segment model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Boolean, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forge_engine.core.database import Base


class Segment(Base):
    """Segment model - represents a detected viral clip segment."""
    
    __tablename__ = "segments"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    
    # Timing
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Content
    topic_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hook_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_segments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Scoring
    score_total: Mapped[float] = mapped_column(Float, default=0.0)
    score_hook: Mapped[float] = mapped_column(Float, default=0.0)
    score_payoff: Mapped[float] = mapped_column(Float, default=0.0)
    score_humour: Mapped[float] = mapped_column(Float, default=0.0)
    score_tension: Mapped[float] = mapped_column(Float, default=0.0)
    score_clarity: Mapped[float] = mapped_column(Float, default=0.0)
    score_rhythm: Mapped[float] = mapped_column(Float, default=0.0)
    score_reasons: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    score_tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Cold open
    cold_open_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    cold_open_start_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Layout
    layout_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    facecam_rect: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_rect: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Variants
    variants: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="segments")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "projectId": self.project_id,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "duration": self.duration,
            "topicLabel": self.topic_label,
            "hookText": self.hook_text,
            "transcript": self.transcript,
            "transcriptSegments": self.transcript_segments,
            "score": {
                "total": self.score_total,
                "hookStrength": self.score_hook,
                "payoff": self.score_payoff,
                "humourReaction": self.score_humour,
                "tensionSurprise": self.score_tension,
                "clarityAutonomy": self.score_clarity,
                "rhythm": self.score_rhythm,
                "reasons": self.score_reasons or [],
                "tags": self.score_tags or [],
            },
            "coldOpenRecommended": self.cold_open_recommended,
            "coldOpenStartTime": self.cold_open_start_time,
            "layoutType": self.layout_type,
            "facecamRect": self.facecam_rect,
            "contentRect": self.content_rect,
            "variants": self.variants,
            "createdAt": self.created_at.isoformat(),
        }


# Import at end to avoid circular imports
from forge_engine.models.project import Project









