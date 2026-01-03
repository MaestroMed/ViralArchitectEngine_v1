"""Intro generation engine for video clips."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from forge_engine.services.ffmpeg import FFmpegService
from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


class IntroEngine:
    """Service for generating video intro sequences with blur, title and badge."""
    
    def __init__(self):
        self.ffmpeg = FFmpegService.get_instance()
        self.output_width = settings.OUTPUT_WIDTH
        self.output_height = settings.OUTPUT_HEIGHT
    
    async def render_intro(
        self,
        source_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Render an intro clip with blurred background, title and badge.
        
        Args:
            source_path: Path to source video
            output_path: Path to output intro clip
            start_time: Start time in source video (to extract background frame)
            duration: Duration of intro in seconds
            config: Intro configuration with:
                - title: Title text to display
                - badgeText: Badge text (e.g., @username)
                - backgroundBlur: Blur intensity (0-30)
                - titleFont: Font family for title
                - titleSize: Font size for title
                - titleColor: Hex color for title
                - badgeColor: Hex color for badge
                - animation: Animation type (fade, slide, zoom, bounce)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract config values
        title = config.get("title", "")
        badge_text = config.get("badgeText", "")
        blur = config.get("backgroundBlur", 15)
        title_font = config.get("titleFont", "Montserrat")
        title_size = config.get("titleSize", 72)
        title_color = self._hex_to_ffmpeg_color(config.get("titleColor", "#FFFFFF"))
        badge_color = self._hex_to_ffmpeg_color(config.get("badgeColor", "#00FF88"))
        animation = config.get("animation", "fade")
        
        # Build filter complex for intro
        # 1. Extract a single frame at start_time
        # 2. Apply blur
        # 3. Scale to output size
        # 4. Loop for duration
        # 5. Overlay text with animation
        
        # Calculate positions
        title_y = int(self.output_height * 0.45)  # 45% from top
        badge_y = int(self.output_height * 0.55)  # 55% from top
        
        # Animation timing
        fade_in = 0.5
        fade_out = 0.3
        
        # Build filter chain
        filters = []
        
        # Background: extract frame, scale, blur, loop
        filters.append(
            f"[0:v]select='eq(n\\,0)',setpts=N/FRAME_RATE/TB,"
            f"scale={self.output_width}:{self.output_height}:force_original_aspect_ratio=increase,"
            f"crop={self.output_width}:{self.output_height},"
            f"boxblur={blur}:{blur},"
            f"loop=loop={int(duration * 30)}:size=1:start=0,"
            f"setpts=N/30/TB[bg]"
        )
        
        # Title text with animation
        title_escaped = title.replace("'", "\\'").replace(":", "\\:")
        title_filter = self._build_text_filter(
            text=title_escaped,
            font=title_font,
            size=title_size,
            color=title_color,
            x="(w-text_w)/2",
            y=str(title_y),
            animation=animation,
            duration=duration,
            fade_in=fade_in,
            layer_name="title"
        )
        filters.append(f"[bg]{title_filter}[withtitle]")
        
        # Badge text
        if badge_text:
            badge_escaped = badge_text.replace("'", "\\'").replace(":", "\\:")
            badge_filter = self._build_text_filter(
                text=badge_escaped,
                font=title_font,
                size=int(title_size * 0.5),
                color=badge_color,
                x="(w-text_w)/2",
                y=str(badge_y),
                animation=animation,
                duration=duration,
                fade_in=fade_in + 0.2,  # Slightly delayed
                layer_name="badge"
            )
            filters.append(f"[withtitle]{badge_filter}[final]")
            final_output = "[final]"
        else:
            final_output = "[withtitle]"
        
        # Add fade out at the end
        filters.append(
            f"{final_output}fade=t=out:st={duration - fade_out}:d={fade_out}[out]"
        )
        
        filter_complex = ";".join(filters)
        
        # Build FFmpeg command
        cmd = [
            str(self.ffmpeg.ffmpeg_path),
            "-ss", str(start_time),
            "-i", source_path,
            "-t", str(duration),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            "-y",
            str(output_path)
        ]
        
        logger.info(f"Rendering intro: {' '.join(cmd)}")
        
        # Run FFmpeg
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        await proc.wait()
        
        if proc.returncode != 0:
            logger.error(f"Intro rendering failed with code {proc.returncode}")
            raise RuntimeError("Intro rendering failed")
        
        if progress_callback:
            progress_callback(100.0)
        
        return {
            "output_path": str(output_path),
            "duration": duration,
        }
    
    def _build_text_filter(
        self,
        text: str,
        font: str,
        size: int,
        color: str,
        x: str,
        y: str,
        animation: str,
        duration: float,
        fade_in: float,
        layer_name: str
    ) -> str:
        """Build drawtext filter with animation."""
        
        # Base drawtext parameters
        base_params = [
            f"text='{text}'",
            f"fontfile={self._get_font_path(font)}",
            f"fontsize={size}",
            f"fontcolor={color}",
            f"x={x}",
            f"y={y}",
            "shadowcolor=black@0.5",
            "shadowx=3",
            "shadowy=3",
        ]
        
        # Add animation based on type
        if animation == "fade":
            # Simple fade in
            base_params.append(f"alpha='if(lt(t,{fade_in}),t/{fade_in},1)'")
        elif animation == "slide":
            # Slide up from below
            base_params[-2] = f"y={y}+50*(1-min(t/{fade_in},1))"
            base_params.append(f"alpha='if(lt(t,{fade_in}),t/{fade_in},1)'")
        elif animation == "zoom":
            # Zoom in effect via fontsize (simplified)
            base_params.append(f"alpha='if(lt(t,{fade_in}),t/{fade_in},1)'")
        elif animation == "bounce":
            # Bounce effect
            bounce_expr = f"if(lt(t,{fade_in}),{y}+30*sin(t*10)*pow(0.5,t*5),{y})"
            base_params[-2] = f"y={bounce_expr}"
            base_params.append(f"alpha='if(lt(t,{fade_in}),t/{fade_in},1)'")
        else:
            base_params.append(f"alpha='if(lt(t,{fade_in}),t/{fade_in},1)'")
        
        return f"drawtext={':'.join(base_params)}"
    
    def _get_font_path(self, font_name: str) -> str:
        """Get font path for FFmpeg.
        
        On Windows, we need to provide full path to font files.
        Falls back to a common system font if not found.
        """
        import platform
        
        font_map = {
            "Inter": "Inter-Bold.ttf",
            "Montserrat": "Montserrat-Bold.ttf",
            "Space Grotesk": "SpaceGrotesk-Bold.ttf",
            "Playfair Display": "PlayfairDisplay-Bold.ttf",
            "Oswald": "Oswald-Bold.ttf",
            "Bebas Neue": "BebasNeue-Regular.ttf",
        }
        
        if platform.system() == "Windows":
            # Windows fonts directory
            fonts_dir = Path("C:/Windows/Fonts")
            
            # Try to find the font
            font_file = font_map.get(font_name, f"{font_name.replace(' ', '')}-Bold.ttf")
            font_path = fonts_dir / font_file
            
            if font_path.exists():
                return str(font_path).replace("\\", "/").replace(":", "\\\\:")
            
            # Fallback to Arial which is always available on Windows
            return "C\\\\:/Windows/Fonts/arial.ttf"
        else:
            # On Linux/Mac, just return the font name and let fontconfig handle it
            return font_name
    
    def _hex_to_ffmpeg_color(self, hex_color: str) -> str:
        """Convert hex color to FFmpeg format (0xRRGGBB or color name)."""
        if not hex_color:
            return "white"
        
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            return f"0x{hex_color}"
        return "white"
    
    async def concat_intro_with_clip(
        self,
        intro_path: str,
        clip_path: str,
        output_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Concatenate intro with main clip."""
        output_path = Path(output_path)
        
        # Create concat file
        concat_file = output_path.parent / f"{output_path.stem}_concat.txt"
        with open(concat_file, "w") as f:
            f.write(f"file '{intro_path}'\n")
            f.write(f"file '{clip_path}'\n")
        
        cmd = [
            str(self.ffmpeg.ffmpeg_path),
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-y",
            str(output_path)
        ]
        
        logger.info(f"Concatenating intro + clip: {' '.join(cmd)}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        await proc.wait()
        
        # Cleanup concat file
        try:
            concat_file.unlink()
        except Exception:
            pass
        
        if proc.returncode != 0:
            raise RuntimeError("Concat failed")
        
        if progress_callback:
            progress_callback(100.0)
        
        return {
            "output_path": str(output_path),
        }

