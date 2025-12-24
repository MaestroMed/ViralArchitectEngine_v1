"""Tests for caption generation service."""

import pytest
from forge_engine.services.captions import CaptionEngine, CAPTION_STYLES


class TestCaptionEngine:
    """Tests for the CaptionEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = CaptionEngine()
    
    def test_styles_exist(self):
        """Verify all expected caption styles exist."""
        expected_styles = ["forge_minimal", "impact_modern", "neon_whisper"]
        
        for style in expected_styles:
            assert style in CAPTION_STYLES
    
    def test_ass_generation_basic(self):
        """Verify basic ASS file generation."""
        segments = [
            {"start": 0, "end": 5, "text": "Hello world"},
            {"start": 5, "end": 10, "text": "This is a test"},
        ]
        
        ass_content = self.engine.generate_ass(segments)
        
        assert "[Script Info]" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "[Events]" in ass_content
        assert "Dialogue:" in ass_content
    
    def test_ass_style_applied(self):
        """Verify style is correctly applied to ASS output."""
        segments = [{"start": 0, "end": 5, "text": "Test"}]
        
        ass_content = self.engine.generate_ass(segments, style_name="forge_minimal")
        
        assert "Style: Default" in ass_content
        assert "Inter" in ass_content  # Font family
    
    def test_word_level_karaoke(self):
        """Verify word-level karaoke timing is generated."""
        segments = [
            {
                "start": 0,
                "end": 5,
                "text": "Hello world test",
                "words": [
                    {"word": "Hello", "start": 0, "end": 1, "confidence": 0.9},
                    {"word": "world", "start": 1.2, "end": 2, "confidence": 0.95},
                    {"word": "test", "start": 2.5, "end": 3, "confidence": 0.85},
                ]
            }
        ]
        
        ass_content = self.engine.generate_ass(segments, word_level=True)
        
        # Should contain karaoke timing tags
        assert "\\k" in ass_content or "\\kf" in ass_content
    
    def test_srt_generation(self):
        """Verify SRT file generation."""
        segments = [
            {"start": 0, "end": 5, "text": "First subtitle"},
            {"start": 5.5, "end": 10, "text": "Second subtitle"},
        ]
        
        srt_content = self.engine.generate_srt(segments)
        
        # SRT format validation
        assert "1\n" in srt_content
        assert "00:00:00,000 --> 00:00:05,000" in srt_content
        assert "First subtitle" in srt_content
        assert "2\n" in srt_content
    
    def test_vtt_generation(self):
        """Verify VTT file generation."""
        segments = [
            {"start": 0, "end": 5, "text": "First cue"},
        ]
        
        vtt_content = self.engine.generate_vtt(segments)
        
        assert "WEBVTT" in vtt_content
        assert "00:00:00.000 --> 00:00:05.000" in vtt_content
    
    def test_time_formatting_ass(self):
        """Verify ASS time formatting is correct."""
        # Format should be H:MM:SS.cc (centiseconds)
        formatted = self.engine._format_time(3661.55)  # 1h 1m 1.55s
        
        assert formatted == "1:01:01.55"
    
    def test_time_formatting_srt(self):
        """Verify SRT time formatting is correct."""
        # Format should be HH:MM:SS,mmm
        formatted = self.engine._format_srt_time(3661.555)
        
        assert formatted == "01:01:01,555"
    
    def test_word_cleaning(self):
        """Verify words are properly cleaned for ASS."""
        # Should escape special characters
        cleaned = self.engine._clean_word(" hello{world} ")
        
        assert cleaned == "hello\\{world\\}"
    
    def test_empty_segments_handled(self):
        """Verify empty segments are handled gracefully."""
        segments = [
            {"start": 0, "end": 5, "text": ""},
            {"start": 5, "end": 10, "text": "Valid text"},
        ]
        
        srt_content = self.engine.generate_srt(segments)
        
        # Should only have one numbered entry
        assert "1\n" in srt_content
        assert "2\n" not in srt_content
    
    def test_text_wrapping(self):
        """Verify text wrapping respects max words per line."""
        segments = [
            {"start": 0, "end": 10, "text": "This is a very long sentence that should be wrapped across multiple lines"}
        ]
        
        srt_content = self.engine.generate_srt(segments, max_words_per_line=4)
        
        # Count lines in the subtitle text portion
        lines = [l for l in srt_content.split("\n") if l and not l[0].isdigit() and "-->" not in l]
        
        # Should have multiple lines
        assert len(lines) >= 2


class TestCaptionStyles:
    """Tests for caption style definitions."""
    
    def test_style_has_required_fields(self):
        """Verify all styles have required fields."""
        required_fields = [
            "font_family", "font_size", "primary_color", 
            "outline_color", "outline_width", "alignment"
        ]
        
        for style_name, style in CAPTION_STYLES.items():
            for field in required_fields:
                assert field in style, f"Style '{style_name}' missing '{field}'"
    
    def test_colors_valid_format(self):
        """Verify color values are in valid ASS format."""
        import re
        ass_color_pattern = r"&H[0-9A-Fa-f]{6,8}"
        
        for style_name, style in CAPTION_STYLES.items():
            for color_field in ["primary_color", "outline_color"]:
                if color_field in style:
                    assert re.match(ass_color_pattern, style[color_field]), \
                        f"Invalid color format in {style_name}.{color_field}"









