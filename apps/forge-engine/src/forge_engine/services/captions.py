"""Caption generation engine for ASS subtitles.

WORLD CLASS SUBTITLES - Un seul style parfait, pas de choix.
Style viral optimisé : MAJUSCULES, jaune/blanc, police bold, effet karaoke visible.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# TikTok-optimized resolution (9:16 vertical)
TIKTOK_WIDTH = 1080
TIKTOK_HEIGHT = 1920

# Font size: 5% of screen height for maximum visibility
DEFAULT_FONT_SIZE = 96  # ~5% of 1920

# Base viral style — Anton, white + yellow active word. Presets below derive
# from it. ASS colours are &HAABBGGRR (AA=00 opaque).
DEFAULT_STYLE = {
    "font_family": "Anton",  # Bold condensed font - highly readable
    "font_size": DEFAULT_FONT_SIZE,
    "primary_color": "&H00FFFFFF",  # White
    "highlight_color": "&H0000FFFF",  # Yellow #FFFF00 (active word)
    "outline_color": "&H00000000",  # Black outline
    "outline_width": 8,  # Thick outline for contrast
    "shadow_depth": 5,  # Strong shadow
    "bold": True,
    "alignment": 5,  # Center of screen
    "margin_v": 960,  # Default center (can be customized)
    "max_words_per_line": 4,  # Ultra-readable chunks
    "active_scale": 110,  # active-word scale (%)
    "active_pop": False,  # eased pop-in (\t) vs static scale
    "all_caps": True,
}

# Selectable dynamic caption styles (the editor's "style" picker). Each derives
# from DEFAULT_STYLE and overrides colour / active-word animation / sizing.
# active_pop=True eases the active word from 100% to active_scale over ~120ms
# (the animated word-pop CapCut/Submagic/Hormozi captions are known for).
CAPTION_PRESETS: dict[str, dict[str, Any]] = {
    # White words, yellow active, gentle static bump — the current look.
    "classic": {**DEFAULT_STYLE},
    # Hormozi "money" style: white words, GREEN active word that pops big.
    "hormozi": {
        **DEFAULT_STYLE, "highlight_color": "&H0066FF00",  # green #00FF66
        "active_scale": 130, "active_pop": True, "outline_width": 10, "shadow_depth": 6,
    },
    # Bouncy cyan pop on the brand colour.
    "pop": {
        **DEFAULT_STYLE, "highlight_color": "&H00F2D933",  # cyan #33D9F2
        "active_scale": 122, "active_pop": True,
    },
    # Clean & restrained: smaller, white-on-white highlight, no pop.
    "minimal": {
        **DEFAULT_STYLE, "font_size": 78, "highlight_color": "&H00FFFFFF",
        "active_scale": 100, "active_pop": False, "outline_width": 5,
        "shadow_depth": 2, "max_words_per_line": 3,
    },
    # Neon: magenta active word with a heavier glow.
    "neon": {
        **DEFAULT_STYLE, "highlight_color": "&H00CB3DFF",  # magenta #FF3DCB
        "active_scale": 124, "active_pop": True, "shadow_depth": 9,
    },
}


def resolve_caption_style(preset: str | None) -> dict[str, Any]:
    """Base style dict for a preset name (falls back to classic/default)."""
    return {**CAPTION_PRESETS.get((preset or "classic").lower(), DEFAULT_STYLE)}


class CaptionEngine:
    """Service for generating WORLD CLASS ASS subtitles."""

    def __init__(self, width: int = TIKTOK_WIDTH, height: int = TIKTOK_HEIGHT):
        self.output_width = width
        self.output_height = height

    def generate_ass(
        self,
        transcript_segments: list[dict[str, Any]],
        style_name: str = "default",  # Ignored - only one style
        custom_style: dict[str, Any] | None = None,
        word_level: bool = True,
        max_words_per_line: int = 4,
        max_lines: int = 2,
        facecam_position: str | None = None
    ) -> str:
        """Generate ASS subtitle file with karaoke effect.

        ``style_name`` selects a caption PRESET (classic/hormozi/pop/minimal/neon);
        ``custom_style`` then overrides position/size/words-per-line on top.
        """
        # Start from the selected preset.
        style = resolve_caption_style(style_name)

        # Layout-aware DEFAULT position: a safe band in the content zone — below
        # the facecam (two-zone vstack), above TikTok's bottom UI, never on the
        # seam. alignment=2 (bottom-center) so margin_v is measured from bottom.
        facecam_ratio = (custom_style or {}).get("facecam_ratio")
        style["alignment"] = 2
        style["margin_v"] = self._safe_margin_v(facecam_ratio)

        # Apply custom position if provided
        if custom_style:
            position_y = custom_style.get("positionY") or custom_style.get("position_y")
            if position_y is not None and position_y > 0:
                # Custom Y position from top - convert to margin_v (from bottom).
                # margin_v is the gap from the bottom edge to the text baseline.
                style["margin_v"] = max(120, self.output_height - int(position_y))
                style["alignment"] = 2  # Bottom-center alignment for margin_v

            # Allow font size override
            font_size = custom_style.get("fontSize") or custom_style.get("font_size")
            if font_size:
                style["font_size"] = max(60, min(font_size, 140))

            # Allow words per line override
            words_per_line = custom_style.get("wordsPerLine") or custom_style.get("words_per_line")
            if words_per_line:
                max_words_per_line = max(2, min(words_per_line, 8))

            # Per-field colour / weight / family / position overrides on top of
            # the preset (camelCase from the editor). Hex #RRGGBB -> ASS via
            # _hex_to_ass_color. Only EXPLICIT keys arrive, so presets aren't
            # clobbered by defaults.
            def _as_color(v: Any) -> Any:
                return self._hex_to_ass_color(v) if isinstance(v, str) and v.startswith("#") else v

            if custom_style.get("color"):
                style["primary_color"] = _as_color(custom_style["color"])
            hl = custom_style.get("highlightColor") or custom_style.get("highlight_color")
            if hl:
                style["highlight_color"] = _as_color(hl)
            oc = custom_style.get("outlineColor") or custom_style.get("outline_color")
            if oc:
                style["outline_color"] = _as_color(oc)
            ow = custom_style.get("outlineWidth", custom_style.get("outline_width"))
            if ow is not None:
                try:
                    style["outline_width"] = max(0, min(int(ow), 16))
                except (TypeError, ValueError):
                    pass
            fw = custom_style.get("fontWeight")
            if fw is not None:
                try:
                    style["bold"] = int(fw) >= 700
                except (TypeError, ValueError):
                    pass
            ff = custom_style.get("fontFamily") or custom_style.get("font_family")
            if ff:
                style["font_family"] = ff
            pos = custom_style.get("position")
            if pos in ("top", "center", "bottom"):
                style["alignment"] = {"top": 8, "center": 5, "bottom": 2}[pos]
                if pos == "top":
                    style["margin_v"] = int(self.output_height * 0.12)
                elif pos == "center":
                    style["margin_v"] = int(self.output_height * 0.5)

        logger.info(f"[Captions] World Class style: font={style['font_family']} size={style['font_size']} margin_v={style['margin_v']}")

        # Build ASS file
        lines = [
            "[Script Info]",
            "Title: FORGE WORLD CLASS Captions",
            "ScriptType: v4.00+",
            f"PlayResX: {self.output_width}",
            f"PlayResY: {self.output_height}",
            "WrapStyle: 0",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            self._generate_style_line("Default", style),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        # Generate dialogue lines with WORLD CLASS karaoke effect
        for segment in transcript_segments:
            if word_level and "words" in segment and segment["words"]:
                dialogue_lines = self._generate_karaoke_captions(
                    segment,
                    style,
                    max_words_per_line
                )
            else:
                dialogue_lines = self._generate_simple_captions(
                    segment,
                    max_words_per_line
                )

            lines.extend(dialogue_lines)

        return "\n".join(lines)

    def _safe_margin_v(self, facecam_ratio: float | None) -> int:
        """Vertical margin (from bottom) placing captions in a safe band:
        below the facecam zone (two-zone vstack), above TikTok's bottom UI."""
        h = self.output_height
        content_top = (facecam_ratio or 0.0) * h
        # Baseline ~78% down, but never above (facecam_top + 300px) and never in
        # the bottom ~16% where TikTok renders its own caption/username UI.
        baseline = max(content_top + 300, h * 0.78)
        baseline = min(baseline, h * 0.84)
        return int(h - baseline)

    def _generate_style_line(self, name: str, style: dict[str, Any]) -> str:
        """Generate ASS style line."""
        bold = -1 if style.get("bold", True) else 0

        return (
            f"Style: {name},"
            f"{style.get('font_family', 'Anton')},"
            f"{style.get('font_size', 96)},"
            f"{style.get('primary_color', '&H00FFFFFF')},"
            f"{style.get('highlight_color', '&H0000FFFF')},"
            f"{style.get('outline_color', '&H00000000')},"
            f"&H80000000,"  # Back color (semi-transparent shadow)
            f"{bold},0,0,0,"  # Bold, Italic, Underline, StrikeOut
            f"100,100,"  # ScaleX, ScaleY
            f"0,0,"  # Spacing, Angle
            f"1,"  # BorderStyle (1 = outline + shadow)
            f"{style.get('outline_width', 8)},"
            f"{style.get('shadow_depth', 5)},"
            f"{style.get('alignment', 5)},"
            f"20,20,"  # MarginL, MarginR
            f"{style.get('margin_v', 960)},"
            f"1"  # Encoding
        )

    def _generate_karaoke_captions(
        self,
        segment: dict[str, Any],
        style: dict[str, Any],
        max_words_per_line: int
    ) -> list[str]:
        """
        Generate WORLD CLASS karaoke captions using multi-dialogue approach.

        Each word timing generates a separate dialogue where:
        - The active word is YELLOW and slightly larger
        - Other words are WHITE
        - ALL TEXT IS IN UPPERCASE
        """
        words = segment.get("words", [])
        if not words:
            return self._generate_simple_captions(segment, max_words_per_line)

        dialogues = []

        # Colours + active-word animation from the resolved preset.
        white = style.get("primary_color", "&H00FFFFFF")
        highlight = style.get("highlight_color", "&H0000FFFF")
        active_scale = int(style.get("active_scale", 110))
        active_pop = bool(style.get("active_pop", False))
        all_caps = bool(style.get("all_caps", True))

        # Group words into chunks for display. Phrase-aware: break at sentence/
        # clause punctuation (. ? ! , ; :) as well as at max_words_per_line, so
        # chunks don't split mid-phrase (avoids "L'É CRIS" style breaks).
        chunks = []
        current_chunk = []

        def _ends_clause(w: str) -> bool:
            return w.rstrip().endswith((".", "?", "!", ",", ";", ":", "…"))

        for word in words:
            current_chunk.append(word)
            raw = word.get("word", "") if isinstance(word, dict) else str(word)
            if len(current_chunk) >= max_words_per_line or (
                _ends_clause(raw) and len(current_chunk) >= 2
            ):
                chunks.append(current_chunk)
                current_chunk = []

        if current_chunk:
            chunks.append(current_chunk)

        # Generate dialogues for each chunk
        for chunk in chunks:
            if not chunk:
                continue

            chunk[0]["start"]
            chunk[-1]["end"]

            # For each word in the chunk, create a dialogue where THAT word is highlighted
            for word_idx, active_word in enumerate(chunk):
                word_start = active_word["start"]
                word_end = active_word["end"]

                # Build the text with inline colour/scale overrides per word.
                text_parts = []
                for i, word in enumerate(chunk):
                    clean = self._clean_word(word["word"])
                    clean_word = clean.upper() if all_caps else clean

                    if i == word_idx:
                        # ACTIVE WORD: highlight colour + scale. With active_pop,
                        # ease from 100% -> active_scale over 120ms (\t) for the
                        # animated word-pop; otherwise a static bump.
                        if active_pop:
                            anim = (
                                f"\\fscx100\\fscy100"
                                f"\\t(0,120,\\fscx{active_scale}\\fscy{active_scale})"
                            )
                        else:
                            anim = f"\\fscx{active_scale}\\fscy{active_scale}"
                        text_parts.append(
                            f"{{\\1c{highlight}{anim}}}{clean_word}{{\\r}}"
                        )
                    else:
                        # Other words: primary colour, normal scale.
                        text_parts.append(
                            f"{{\\1c{white}}}{clean_word}{{\\r}}"
                        )

                text = " ".join(text_parts)

                # Add fade effect at chunk boundaries
                if word_idx == 0:
                    text = "{\\fad(50,0)}" + text
                elif word_idx == len(chunk) - 1:
                    text = "{\\fad(0,80)}" + text

                dialogues.append(
                    f"Dialogue: 0,{self._format_time(word_start)},{self._format_time(word_end)},"
                    f"Default,,0,0,0,,{text}"
                )

        return dialogues

    def _generate_simple_captions(
        self,
        segment: dict[str, Any],
        max_words_per_line: int
    ) -> list[str]:
        """Generate simple phrase-level captions (fallback when no word timing)."""
        text = segment.get("text", "").strip().upper()  # UPPERCASE
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

        # Limit lines
        if len(wrapped_lines) > 2:
            wrapped_lines = wrapped_lines[:2]

        display_text = "\\N".join(wrapped_lines)
        display_text = "{\\fad(100,100)}" + display_text

        return [
            f"Dialogue: 0,{self._format_time(start)},{self._format_time(end)},"
            f"Default,,0,0,0,,{display_text}"
        ]

    def _clean_word(self, word: str) -> str:
        """Clean a word for display."""
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

    def _hex_to_ass_color(self, hex_color: str) -> str:
        """Convert hex color (#RRGGBB) to ASS format (&H00BBGGRR)."""
        if not hex_color or hex_color == "transparent":
            return "&H00000000"

        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"&H00{b:02X}{g:02X}{r:02X}"
        return "&H00FFFFFF"

    # ============ OTHER FORMATS ============

    def generate_srt(
        self,
        transcript_segments: list[dict[str, Any]],
        max_words_per_line: int = 6
    ) -> str:
        """Generate SRT subtitle file content."""
        lines = []

        for i, segment in enumerate(transcript_segments, 1):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip().upper()  # UPPERCASE

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
        transcript_segments: list[dict[str, Any]],
        max_words_per_line: int = 6
    ) -> str:
        """Generate VTT subtitle file content."""
        lines = ["WEBVTT", ""]

        for segment in transcript_segments:
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip().upper()  # UPPERCASE

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
        transcript_segments: list[dict[str, Any]],
        output_dir: Path,
        base_name: str = "captions",
        style_name: str = "default"
    ) -> dict[str, str]:
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
