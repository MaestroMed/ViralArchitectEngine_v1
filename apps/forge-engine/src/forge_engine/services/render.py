"""Video render service."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from forge_engine.core.config import settings
from forge_engine.services.ffmpeg import FFmpegService
from forge_engine.services.captions import CaptionEngine

logger = logging.getLogger(__name__)


class RenderService:
    """Service for rendering final video clips."""
    
    def __init__(self):
        self.ffmpeg = FFmpegService()
        self.captions = CaptionEngine()
    
    async def render_clip(
        self,
        source_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        layout_config: Dict[str, Any],
        caption_config: Optional[Dict[str, Any]] = None,
        transcript_segments: Optional[List[Dict[str, Any]]] = None,
        hook_card_config: Optional[Dict[str, Any]] = None,
        use_nvenc: bool = True,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Render a clip with all effects."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build filter chain
        filters = []
        
        # Composition filter
        facecam_rect = layout_config.get("facecam_rect")
        content_rect = layout_config.get("content_rect")
        
        if facecam_rect and content_rect:
            comp_filters = self.ffmpeg.build_composition_filter(
                facecam_rect=facecam_rect,
                content_rect=content_rect,
                output_width=settings.OUTPUT_WIDTH,
                output_height=settings.OUTPUT_HEIGHT,
                facecam_ratio=layout_config.get("facecam_ratio", 0.4),
                background_blur=layout_config.get("background_blur", True)
            )
            filters.extend(comp_filters)
        
        # Generate ASS captions if transcript provided
        ass_path = None
        if transcript_segments and caption_config:
            # Filter transcript to segment time range
            segment_transcript = [
                seg for seg in transcript_segments
                if start_time <= seg.get("start", 0) <= start_time + duration
            ]
            
            # Adjust times to be relative to clip start
            adjusted_transcript = []
            for seg in segment_transcript:
                adjusted_transcript.append({
                    **seg,
                    "start": seg["start"] - start_time,
                    "end": seg["end"] - start_time,
                    "words": [
                        {
                            **w,
                            "start": w["start"] - start_time,
                            "end": w["end"] - start_time
                        }
                        for w in seg.get("words", [])
                    ] if seg.get("words") else None
                })
            
            if adjusted_transcript:
                # Generate ASS file
                ass_content = self.captions.generate_ass(
                    adjusted_transcript,
                    style_name=caption_config.get("style", "forge_minimal"),
                    word_level=caption_config.get("word_level", True),
                    max_words_per_line=caption_config.get("max_words_per_line", 6),
                    max_lines=caption_config.get("max_lines", 2)
                )
                
                # Save temp ASS file
                ass_path = output_path.parent / f"{output_path.stem}_captions.ass"
                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(ass_content)
        
        # Render video
        success = await self.ffmpeg.render_clip(
            input_path=source_path,
            output_path=str(output_path),
            start_time=start_time,
            duration=duration,
            filters=filters,
            ass_path=str(ass_path) if ass_path else None,
            use_nvenc=use_nvenc and not settings.FORCE_CPU,
            crf=settings.OUTPUT_CRF,
            width=settings.OUTPUT_WIDTH,
            height=settings.OUTPUT_HEIGHT,
            fps=settings.OUTPUT_FPS,
            progress_callback=progress_callback
        )
        
        if not success:
            raise RuntimeError("Video rendering failed")
        
        # Clean up temp ASS file
        if ass_path and ass_path.exists():
            # Keep it for debugging, but could delete
            pass
        
        return {
            "output_path": str(output_path),
            "duration": duration,
            "ass_path": str(ass_path) if ass_path else None,
        }
    
    async def render_cover(
        self,
        source_path: str,
        output_path: str,
        time: float,
        title_text: Optional[str] = None,
        style: str = "default"
    ) -> bool:
        """Render a cover image for the clip."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract frame
        success = await self.ffmpeg.extract_frame(
            input_path=source_path,
            output_path=str(output_path),
            time=time,
            width=settings.OUTPUT_WIDTH,
            height=settings.OUTPUT_HEIGHT
        )
        
        if not success:
            return False
        
        # Optionally add title overlay
        if title_text:
            try:
                from PIL import Image, ImageDraw, ImageFont
                
                img = Image.open(output_path)
                draw = ImageDraw.Draw(img)
                
                # Try to load a nice font
                try:
                    font = ImageFont.truetype("arial.ttf", 48)
                except Exception:
                    font = ImageFont.load_default()
                
                # Add semi-transparent overlay at bottom
                overlay_height = 200
                overlay = Image.new("RGBA", (img.width, overlay_height), (0, 0, 0, 180))
                
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                
                img.paste(overlay, (0, img.height - overlay_height), overlay)
                
                # Draw title
                draw = ImageDraw.Draw(img)
                
                # Wrap text
                max_width = img.width - 40
                words = title_text.split()
                lines = []
                current_line = []
                
                for word in words:
                    test_line = " ".join(current_line + [word])
                    bbox = draw.textbbox((0, 0), test_line, font=font)
                    if bbox[2] - bbox[0] > max_width:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        current_line.append(word)
                
                if current_line:
                    lines.append(" ".join(current_line))
                
                # Draw lines
                y = img.height - overlay_height + 20
                for line in lines[:3]:  # Max 3 lines
                    bbox = draw.textbbox((0, 0), line, font=font)
                    x = (img.width - (bbox[2] - bbox[0])) // 2
                    draw.text((x, y), line, font=font, fill=(255, 255, 255))
                    y += bbox[3] - bbox[1] + 10
                
                # Save
                img.convert("RGB").save(output_path, quality=95)
                
            except ImportError:
                logger.warning("PIL not available, cover saved without title overlay")
        
        return True
    
    async def render_proxy(
        self,
        source_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        layout_config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """Render a quick proxy preview."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Simpler filter chain for proxy
        filters = ["scale=540:960"]
        
        # Use fast preset
        success = await self.ffmpeg.render_clip(
            input_path=source_path,
            output_path=str(output_path),
            start_time=start_time,
            duration=duration,
            filters=filters,
            ass_path=None,
            use_nvenc=True,  # NVENC is fast for proxies
            crf=28,
            width=540,
            height=960,
            fps=30,
            progress_callback=progress_callback
        )
        
        return success









