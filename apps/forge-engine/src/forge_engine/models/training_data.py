"""Database models for ML training data."""

from datetime import datetime
from forge_engine.core.timeutils import utcnow

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from forge_engine.core.database import Base


class SegmentFeedback(Base):
    """User feedback on a segment for ML training."""

    __tablename__ = "segment_feedback"

    id = Column(String(36), primary_key=True)
    segment_id = Column(String(36), ForeignKey("segments.id"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)

    # Feedback data
    rating = Column(Float, nullable=False)  # 0-10 user rating
    feedback_type = Column(String(50), default="user")  # user, performance, auto

    # Performance metrics (if from analytics)
    views = Column(Integer, nullable=True)
    likes = Column(Integer, nullable=True)
    shares = Column(Integer, nullable=True)
    comments = Column(Integer, nullable=True)
    watch_time_avg = Column(Float, nullable=True)  # Average watch time in seconds
    completion_rate = Column(Float, nullable=True)  # 0-1

    # Extracted features (JSON)
    features_json = Column(Text, nullable=True)

    # Metadata
    platform = Column(String(50), nullable=True)  # tiktok, youtube, instagram
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    segment = relationship("Segment", back_populates="feedback")


class MLModelVersion(Base):
    """Track ML model versions."""

    __tablename__ = "ml_model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)

    # Model info
    model_type = Column(String(100), nullable=False)
    training_examples = Column(Integer, nullable=False)
    cv_score = Column(Float, nullable=False)

    # Feature importance (JSON)
    feature_importances_json = Column(Text, nullable=True)

    # Files
    model_path = Column(String(500), nullable=True)
    scaler_path = Column(String(500), nullable=True)

    # Status
    is_active = Column(Integer, default=1)  # SQLite doesn't have bool

    # Metadata
    trained_at = Column(DateTime, default=utcnow)
    notes = Column(Text, nullable=True)


# Note: Add to Segment model in models/__init__.py:
# feedback = relationship("SegmentFeedback", back_populates="segment")
