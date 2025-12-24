"""Profile model."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from forge_engine.core.database import Base


class Profile(Base):
    """Profile model - creator presets and preferences."""
    
    __tablename__ = "profiles"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Custom dictionary for transcription
    custom_dictionary: Mapped[list] = mapped_column(JSON, default=list)
    
    # Preferences
    preferred_caption_style: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    preferred_layout: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Target duration
    target_duration: Mapped[dict] = mapped_column(
        JSON, 
        default={"min": 15, "max": 60, "optimal": 30}
    )
    
    # Patterns
    hook_patterns: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    content_tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Flags
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "customDictionary": self.custom_dictionary,
            "preferredCaptionStyle": self.preferred_caption_style,
            "preferredLayout": self.preferred_layout,
            "targetDuration": self.target_duration,
            "hookPatterns": self.hook_patterns,
            "contentTags": self.content_tags,
            "isDefault": self.is_default,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }









