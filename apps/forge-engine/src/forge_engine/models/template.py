"""Template and CaptionStyle models."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from forge_engine.core.database import Base


class CaptionStyle(Base):
    """Caption style model."""
    
    __tablename__ = "caption_styles"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Typography
    font_family: Mapped[str] = mapped_column(String(100), default="Inter")
    font_size: Mapped[int] = mapped_column(Integer, default=48)
    font_weight: Mapped[str] = mapped_column(String(20), default="bold")
    
    # Colors
    primary_color: Mapped[str] = mapped_column(String(9), default="#FFFFFF")
    outline_color: Mapped[str] = mapped_column(String(9), default="#000000")
    outline_width: Mapped[float] = mapped_column(Float, default=3.0)
    shadow_color: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    shadow_offset_x: Mapped[float] = mapped_column(Float, default=2.0)
    shadow_offset_y: Mapped[float] = mapped_column(Float, default=2.0)
    highlight_color: Mapped[Optional[str]] = mapped_column(String(9), nullable=True)
    
    # Style
    highlight_style: Mapped[str] = mapped_column(String(20), default="karaoke")
    alignment: Mapped[str] = mapped_column(String(10), default="center")
    vertical_position: Mapped[float] = mapped_column(Float, default=75.0)
    max_lines: Mapped[int] = mapped_column(Integer, default=2)
    words_per_line: Mapped[int] = mapped_column(Integer, default=6)
    animation: Mapped[str] = mapped_column(String(20), default="pop")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "fontFamily": self.font_family,
            "fontSize": self.font_size,
            "fontWeight": self.font_weight,
            "primaryColor": self.primary_color,
            "outlineColor": self.outline_color,
            "outlineWidth": self.outline_width,
            "shadowColor": self.shadow_color,
            "shadowOffset": {"x": self.shadow_offset_x, "y": self.shadow_offset_y},
            "highlightColor": self.highlight_color,
            "highlightStyle": self.highlight_style,
            "alignment": self.alignment,
            "verticalPosition": self.vertical_position,
            "maxLines": self.max_lines,
            "wordsPerLine": self.words_per_line,
            "animation": self.animation,
        }


class Template(Base):
    """Template model for export presets."""
    
    __tablename__ = "templates"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Caption style (embedded JSON)
    caption_style: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Layout config
    layout: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Hook card style
    hook_card_style: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Brand kit
    brand_kit: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
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
            "captionStyle": self.caption_style,
            "layout": self.layout,
            "hookCardStyle": self.hook_card_style,
            "brandKit": self.brand_kit,
            "isDefault": self.is_default,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }









