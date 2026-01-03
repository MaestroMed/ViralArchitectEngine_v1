"""Project model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from forge_engine.core.database import Base


class Project(Base):
    """Project model - represents a VOD import and its processing state."""
    
    __tablename__ = "projects"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Source file info
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    audio_tracks: Mapped[int] = mapped_column(Integer, default=1)
    
    # Generated files
    proxy_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20), 
        default="created",
        nullable=False
    )  # created, ingesting, ingested, analyzing, analyzed, ready, error
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Profile reference
    profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Extra metadata
    project_meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    segments: Mapped[list["Segment"]] = relationship(
        "Segment",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "sourcePath": self.source_path,
            "sourceFilename": self.source_filename,
            "duration": self.duration,
            "resolution": {"width": self.width, "height": self.height} if self.width else None,
            "fps": self.fps,
            "audioTracks": self.audio_tracks,
            "proxyPath": self.proxy_path,
            "audioPath": self.audio_path,
            "thumbnailPath": self.thumbnail_path,
            "status": self.status,
            "errorMessage": self.error_message,
            "profileId": self.profile_id,
            "metadata": self.project_meta,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


# Import at end to avoid circular imports
from forge_engine.models.segment import Segment
from forge_engine.models.artifact import Artifact

