"""Artifact model for exported files."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forge_engine.core.database import Base


class Artifact(Base):
    """Artifact model - represents an exported file."""
    
    __tablename__ = "artifacts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # Variant info
    variant: Mapped[str] = mapped_column(String(1), nullable=False)  # A, B, C
    
    # File info
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # video, cover, captions_srt, etc.
    path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0)
    
    # Optional metadata
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="artifacts")
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "projectId": self.project_id,
            "segmentId": self.segment_id,
            "variant": self.variant,
            "type": self.type,
            "path": self.path,
            "filename": self.filename,
            "size": self.size,
            "title": self.title,
            "description": self.description,
            "createdAt": self.created_at.isoformat(),
        }


# Import at end to avoid circular imports
from forge_engine.models.project import Project









