"""Export profile model for storing user presets."""

from datetime import datetime
from forge_engine.core.timeutils import utcnow

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from forge_engine.core.database import Base


class ExportProfile(Base):
    """Export profile model - stores user presets for batch exports."""

    __tablename__ = "export_profiles"

    id: str = Column(String(36), primary_key=True)
    name: str = Column(String(255), nullable=False)
    description: str | None = Column(String(1000), nullable=True)
    is_default: bool = Column(Boolean, default=False)

    # Layout configuration
    layout_config: dict = Column(SQLiteJSON, default=dict)

    # Subtitle style
    subtitle_style: dict = Column(SQLiteJSON, default=dict)

    # Intro configuration
    intro_config: dict = Column(SQLiteJSON, default=dict)

    # Music settings
    music_config: dict = Column(SQLiteJSON, default=dict)

    # Export settings
    export_settings: dict = Column(SQLiteJSON, default=lambda: {
        "format": "mp4",
        "resolution": "1080x1920",
        "quality": "high",
        "use_nvenc": True,
        "burn_subtitles": True,
        "include_cover": True,
    })

    # Segment filter settings for auto-export
    segment_filters: dict = Column(SQLiteJSON, default=lambda: {
        "min_score": 50,
        "min_duration": 30,
        "max_duration": 180,
        "auto_export_count": 0,  # 0 = disabled
    })

    created_at: datetime = Column(DateTime, default=utcnow)
    updated_at: datetime = Column(DateTime, default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_default": self.is_default,
            "layout_config": self.layout_config or {},
            "subtitle_style": self.subtitle_style or {},
            "intro_config": self.intro_config or {},
            "music_config": self.music_config or {},
            "export_settings": self.export_settings or {},
            "segment_filters": self.segment_filters or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
