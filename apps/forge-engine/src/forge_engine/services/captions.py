"""Caption generation engine for ASS subtitles."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ASS Style Templates
CAPTION_STYLES = {
    "forge_minimal": {
        "font_family": "Inter",
        "font_size": 48,
        "primary_color": "&H00FFFFFF",  # White
        "outline_color": "&H00000000",  # Black
        "outline_width": 3,
        "shadow_depth": 2,
        "bold": True,
        "alignment": 2,  # Bottom center
        "margin_v": 180,
    },
    "impact_modern": {
        "font_family": "Impact",
        "font_size": 56,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 4,
        "shadow_depth": 3,
        "bold": False,
        "alignment": 2,
        "margin_v": 200,
    },
    "neon_whisper": {
        "font_family": "Arial",
        "font_size": 44,
        "primary_color": "&H00FFFF00",  # Cyan
        "outline_color": "&H00FF00FF",  # Magenta
        "outline_width": 2,
        "shadow_depth": 0,
        "bold": True,
        "alignment": 2,
        "margin_v": 180,
    },
}


class CaptionEngine:
    """Service for generating premium ASS subtitles."""
    
    def __init__(self):
        self.output_width = 1080
        self.output_height = 1920
        self.safe_margin_top = 60
        self.safe_margin_bottom = 100
    
    def generate_ass(
        self,
        transcript_segments: List[Dict[str, Any]],
        style_name: str = "forge_minimal",
        custom_style: Optional[Dict[str, Any]] = None,
        word_level: bool = True,
        max_words_per_line: int = 6,
        max_lines: int = 2
    ) -> str:
        """Generate ASS subtitle file content."""
        style = CAPTION_STYLES.get(style_name, CAPTION_STYLES["forge_minimal"]).copy()
        
        if custom_style:
            # Convert custom style to ASS format (handle both camelCase and snake_case)
            font_family = custom_style.get("fontFamily") or custom_style.get("font_family")
            if font_family:
                style["font_family"] = font_family
            
            font_size = custom_style.get("fontSize") or custom_style.get("font_size")
            if font_size:
                style["font_size"] = font_size
            
            font_weight = custom_style.get("fontWeight") or custom_style.get("font_weight")
            if font_weight:
                style["bold"] = font_weight >= 600
            
            color = custom_style.get("color")
            if color:
                style["primary_color"] = self._hex_to_ass_color(color)
            
            outline_color = custom_style.get("outlineColor") or custom_style.get("outline_color")
            if outline_color:
                style["outline_color"] = self._hex_to_ass_color(outline_color)
            
            outline_width = custom_style.get("outlineWidth") or custom_style.get("outline_width")
            if outline_width:
                style["outline_width"] = outline_width
            
            highlight_color = custom_style.get("highlightColor") or custom_style.get("highlight_color")
            if highlight_color:
                style["highlight_color"] = self._hex_to_ass_color(highlight_color)
            
            # Handle positionY (custom absolute Y position)
            position_y = custom_style.get("positionY") or custom_style.get("position_y")
            if position_y is not None and position_y > 0:
                # positionY is distance from TOP in pixels (0-1920)
                # ASS uses alignment + margin_v
                # For subtitles, we use alignment=2 (bottom center) and margin_v from bottom
                # margin_v = distance from BOTTOM edge
                # So margin_v = 1920 - positionY - subtitle_height (approx 60px for text)
                style["alignment"] = 2  # Bottom center
                style["margin_v"] = max(0, self.output_height - position_y - 60)
                logger.debug(f"Custom positionY={position_y} -> margin_v={style['margin_v']}")
            else:
                position = custom_style.get("position")
                if position:
                    # ASS alignment: 1=bottom-left, 2=bottom-center, 5=center, 8=top-center
                    pos_map = {"bottom": 2, "center": 5, "top": 8}
                    style["alignment"] = pos_map.get(position, 2)
                    # Adjust margin for position
                    margin_map = {"bottom": 180, "center": 500, "top": 120}
                    style["margin_v"] = margin_map.get(position, 180)
        
        # Build ASS file
        lines = [
            "[Script Info]",
            "Title: FORGE Captions",
            "ScriptType: v4.00+",
            f"PlayResX: {self.output_width}",
            f"PlayResY: {self.output_height}",
            "WrapStyle: 0",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            self._generate_style_line("Default", style),
            self._generate_style_line("Highlight", {**style, "primary_color": style.get("highlight_color", "&H0000FFFF")}),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        
        # Generate dialogue lines
        for segment in transcript_segments:
            if word_level and "words" in segment:
                # Word-level timing with karaoke effect
                dialogue_lines = self._generate_word_level_captions(
                    segment,
                    style,
                    max_words_per_line,
                    max_lines
                )
            else:
                # Phrase-level captions
                dialogue_lines = self._generate_phrase_captions(
                    segment,
                    max_words_per_line,
                    max_lines
                )
            
            lines.extend(dialogue_lines)
        
        return "\n".join(lines)
    
    def _generate_style_line(self, name: str, style: Dict[str, Any]) -> str:
        """Generate ASS style line."""
        bold = -1 if style.get("bold", True) else 0
        
        return (
            f"Style: {name},"
            f"{style.get('font_family', 'Inter')},"
            f"{style.get('font_size', 48)},"
            f"{style.get('primary_color', '&H00FFFFFF')},"
            f"&H000000FF,"  # Secondary color (not used)
            f"{style.get('outline_color', '&H00000000')},"
            f"&H80000000,"  # Back color
            f"{bold},0,0,0,"  # Bold, Italic, Underline, StrikeOut
            f"100,100,"  # ScaleX, ScaleY
            f"0,0,"  # Spacing, Angle
            f"1,"  # BorderStyle (1 = outline + drop shadow)
            f"{style.get('outline_width', 3)},"
            f"{style.get('shadow_depth', 2)},"
            f"{style.get('alignment', 2)},"
            f"20,20,"  # MarginL, MarginR
            f"{style.get('margin_v', 180)},"
            f"1"  # Encoding
        )
    
    def _generate_word_level_captions(
        self,
        segment: Dict[str, Any],
        style: Dict[str, Any],
        max_words_per_line: int,
        max_lines: int
    ) -> List[str]:
        """Generate word-by-word karaoke captions."""
        words = segment.get("words", [])
        if not words:
            return self._generate_phrase_captions(segment, max_words_per_line, max_lines)
        
        lines = []
        
        # Group words into display chunks
        chunks = []
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= max_words_per_line:
                chunks.append(current_chunk)
                current_chunk = []
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Generate dialogue for each chunk
        for chunk in chunks:
            if not chunk:
                continue
            
            start_time = chunk[0]["start"]
            end_time = chunk[-1]["end"]
            
            # Build karaoke text with timing tags
            text_parts = []
            prev_end = start_time
            
            for word in chunk:
                word_duration = int((word["end"] - word["start"]) * 100)  # centiseconds
                gap = int((word["start"] - prev_end) * 100)
                
                if gap > 0:
                    text_parts.append(f"{{\\k{gap}}}")
                
                # Clean word and add karaoke timing
                clean_word = self._clean_word(word["word"])
                text_parts.append(f"{{\\kf{word_duration}}}{clean_word}")
                
                prev_end = word["end"]
            
            text = " ".join(text_parts).replace("  ", " ")
            
            # Add pop animation
            text = "{\\fad(100,100)}" + text
            
            lines.append(
                f"Dialogue: 0,{self._format_time(start_time)},{self._format_time(end_time)},"
                f"Default,,0,0,0,,{text}"
            )
        
        return lines
    
    def _generate_phrase_captions(
        self,
        segment: Dict[str, Any],
        max_words_per_line: int,
        max_lines: int
    ) -> List[str]:
        """Generate phrase-level captions."""
        text = segment.get("text", "").strip()
        start = segment.get("start", 0)
        end = segment.get("end", 0)
        
        if not text:
            return []
        
        # Wrap text
        words = text.split()
        wrapped_lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            if len(current_line) >= max_words_per_line:
                wrapped_lines.append(" ".join(current_line))
                current_line = []
        
        if current_line:
            wrapped_lines.append(" ".join(current_line))
        
        # Limit to max lines
        if len(wrapped_lines) > max_lines:
            wrapped_lines = wrapped_lines[:max_lines]
            wrapped_lines[-1] += "..."
        
        display_text = "\\N".join(wrapped_lines)
        
        # Add fade animation
        display_text = "{\\fad(150,150)}" + display_text
        
        return [
            f"Dialogue: 0,{self._format_time(start)},{self._format_time(end)},"
            f"Default,,0,0,0,,{display_text}"
        ]
    
    def _hex_to_ass_color(self, hex_color: str) -> str:
        """Convert hex color (#RRGGBB) to ASS format (&HAABBGGRR)."""
        if not hex_color or hex_color == "transparent":
            return "&H00000000"
        
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            # ASS uses AABBGGRR format (alpha, blue, green, red)
            return f"&H00{b:02X}{g:02X}{r:02X}"
        return "&H00FFFFFF"
    
    def _clean_word(self, word: str) -> str:
        """Clean a word for display."""
        # Remove extra whitespace
        word = word.strip()
        # Escape ASS special characters
        word = word.replace("\\", "\\\\")
        word = word.replace("{", "\\{")
        word = word.replace("}", "\\}")
        return word
    
    def _format_time(self, seconds: float) -> str:
        """Format time for ASS (H:MM:SS.cc)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        centiseconds = int((secs % 1) * 100)
        secs = int(secs)
        
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"
    
    def generate_srt(
        self,
        transcript_segments: List[Dict[str, Any]],
        max_words_per_line: int = 8
    ) -> str:
        """Generate SRT subtitle file content."""
        lines = []
        
        for i, segment in enumerate(transcript_segments, 1):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()
            
            if not text:
                continue
            
            # Wrap text
            words = text.split()
            wrapped = []
            current = []
            
            for word in words:
                current.append(word)
                if len(current) >= max_words_per_line:
                    wrapped.append(" ".join(current))
                    current = []
            
            if current:
                wrapped.append(" ".join(current))
            
            lines.append(str(i))
            lines.append(f"{self._format_srt_time(start)} --> {self._format_srt_time(end)}")
            lines.extend(wrapped)
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_vtt(
        self,
        transcript_segments: List[Dict[str, Any]],
        max_words_per_line: int = 8
    ) -> str:
        """Generate VTT subtitle file content."""
        lines = ["WEBVTT", ""]
        
        for i, segment in enumerate(transcript_segments, 1):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()
            
            if not text:
                continue
            
            # Wrap text
            words = text.split()
            wrapped = []
            current = []
            
            for word in words:
                current.append(word)
                if len(current) >= max_words_per_line:
                    wrapped.append(" ".join(current))
                    current = []
            
            if current:
                wrapped.append(" ".join(current))
            
            lines.append(f"{self._format_vtt_time(start)} --> {self._format_vtt_time(end)}")
            lines.extend(wrapped)
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_srt_time(self, seconds: float) -> str:
        """Format time for SRT (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _format_vtt_time(self, seconds: float) -> str:
        """Format time for VTT (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
    
    def save_captions(
        self,
        transcript_segments: List[Dict[str, Any]],
        output_dir: Path,
        base_name: str = "captions",
        style_name: str = "forge_minimal"
    ) -> Dict[str, str]:
        """Save captions in multiple formats."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        paths = {}
        
        # ASS
        ass_content = self.generate_ass(transcript_segments, style_name)
        ass_path = output_dir / f"{base_name}.ass"
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        paths["ass"] = str(ass_path)
        
        # SRT
        srt_content = self.generate_srt(transcript_segments)
        srt_path = output_dir / f"{base_name}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        paths["srt"] = str(srt_path)
        
        # VTT
        vtt_content = self.generate_vtt(transcript_segments)
        vtt_path = output_dir / f"{base_name}.vtt"
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(vtt_content)
        paths["vtt"] = str(vtt_path)
        
        return paths









