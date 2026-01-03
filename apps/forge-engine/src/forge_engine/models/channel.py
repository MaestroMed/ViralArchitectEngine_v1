"""Channel model for monitoring."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from forge_engine.core.database import Base


class WatchedChannel(Base):
    """Model for channels being monitored for new VODs."""
    
    __tablename__ = "watched_channels"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Channel info
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # twitch, youtube
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Monitoring config
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    check_interval: Mapped[int] = mapped_column(Integer, default=3600)  # seconds, default 1 hour
    auto_import: Mapped[bool] = mapped_column(Boolean, default=False)  # Auto-import new VODs
    
    # State
    last_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_vod_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Cache of known VOD IDs
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channelId": self.channel_id,
            "channelName": self.channel_name,
            "displayName": self.display_name,
            "platform": self.platform,
            "profileImageUrl": self.profile_image_url,
            "enabled": self.enabled,
            "checkInterval": self.check_interval,
            "autoImport": self.auto_import,
            "lastCheckAt": self.last_check_at.isoformat() if self.last_check_at else None,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


class DetectedVOD(Base):
    """Model for VODs detected during monitoring."""
    
    __tablename__ = "detected_vods"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # VOD info
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Platform-specific ID
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # seconds
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="new")  # new, imported, ignored
    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # If imported
    
    # Scoring (estimated before import)
    estimated_score: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "externalId": self.external_id,
            "title": self.title,
            "channelId": self.channel_id,
            "channelName": self.channel_name,
            "platform": self.platform,
            "url": self.url,
            "thumbnailUrl": self.thumbnail_url,
            "duration": self.duration,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "viewCount": self.view_count,
            "status": self.status,
            "projectId": self.project_id,
            "estimatedScore": self.estimated_score,
            "detectedAt": self.detected_at.isoformat(),
        }

