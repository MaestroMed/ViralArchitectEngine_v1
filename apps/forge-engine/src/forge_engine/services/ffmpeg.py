"""FFmpeg service for video processing."""

import asyncio
import json
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


class FFmpegService:
    """Service for FFmpeg operations."""
    
    _instance: Optional["FFmpegService"] = None
    _initialized: bool = False
    
    def __init__(self):
        self.ffmpeg_path = settings.FFMPEG_PATH
        self.ffprobe_path = settings.FFPROBE_PATH
        self.version: Optional[str] = None
        self.has_nvenc: bool = False
        self.has_libass: bool = False
        self.available_encoders: List[str] = []
    
    @classmethod
    def get_instance(cls) -> "FFmpegService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def check_availability(self) -> bool:
        """Check if FFmpeg is available and get capabilities."""
        if self._initialized:
            return self.version is not None
        
        try:
            # Get version
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_path, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode != 0:
                return False
            
            # Parse version
            output = stdout.decode()
            match = re.search(r"ffmpeg version (\S+)", output)
            if match:
                self.version = match.group(1)
            
            # Check encoders
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_path, "-encoders",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            encoders_output = stdout.decode()
            
            self.has_nvenc = "h264_nvenc" in encoders_output
            self.available_encoders = []
            
            for line in encoders_output.split("\n"):
                if line.strip().startswith("V"):
                    parts = line.split()
                    if len(parts) >= 2:
                        self.available_encoders.append(parts[1])
            
            # Check filters for libass
            proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_path, "-filters",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            filters_output = stdout.decode()
            self.has_libass = "ass" in filters_output
            
            self._initialized = True
            logger.info(
                "FFmpeg %s initialized - NVENC: %s, libass: %s",
                self.version, self.has_nvenc, self.has_libass
            )
            return True
            
        except Exception as e:
            logger.error("FFmpeg check failed: %s", e)
            return False
    
    async def probe(self, file_path: str) -> Dict[str, Any]:
        """Get media file information using ffprobe."""
        proc = await asyncio.create_subprocess_exec(
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {stderr.decode()}")
        
        return json.loads(stdout.decode())
    
    async def get_video_info(self, file_path: str) -> Dict[str, Any]:
        """Get video file information."""
        probe_data = await self.probe(file_path)
        
        video_stream = None
        audio_streams = []
        
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
            elif stream.get("codec_type") == "audio":
                audio_streams.append(stream)
        
        if not video_stream:
            raise ValueError("No video stream found")
        
        # Calculate duration
        duration = float(probe_data.get("format", {}).get("duration", 0))
        if duration == 0 and video_stream.get("duration"):
            duration = float(video_stream["duration"])
        
        # Calculate FPS
        fps = 30.0
        if video_stream.get("r_frame_rate"):
            num, den = map(int, video_stream["r_frame_rate"].split("/"))
            if den > 0:
                fps = num / den
        
        return {
            "width": video_stream.get("width", 0),
            "height": video_stream.get("height", 0),
            "duration": duration,
            "fps": fps,
            "codec": video_stream.get("codec_name"),
            "audio_tracks": len(audio_streams),
            "format": probe_data.get("format", {}).get("format_name"),
        }
    
    async def create_proxy(
        self,
        input_path: str,
        output_path: str,
        width: int = 1280,
        height: int = 720,
        crf: int = 28,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Create a proxy video file using GPU if available."""
        # Build filter for scaling
        scale_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        
        # Check availability if not done
        if not self._initialized:
            await self.check_availability()
        
        # Use NVENC (GPU) if available for much faster encoding
        if self.has_nvenc:
            logger.info("Using NVENC (GPU) for proxy creation")
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", input_path,
                "-vf", scale_filter,
                "-c:v", "h264_nvenc",
                "-preset", "p4",  # Fast preset (p1=fastest, p7=slowest)
                "-cq", str(crf),  # Quality level
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            logger.info("Using CPU (libx264) for proxy creation")
            cmd = [
                self.ffmpeg_path,
                "-y",
                "-i", input_path,
                "-vf", scale_filter,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", str(crf),
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        
        return await self._run_ffmpeg(cmd, input_path, progress_callback)
    
    async def extract_audio(
        self,
        input_path: str,
        output_path: str,
        sample_rate: int = 16000,
        channels: int = 1,
        audio_track: int = 0,
        normalize: bool = True,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Extract audio from video file."""
        filters = []
        
        if normalize:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", input_path,
            "-map", f"0:a:{audio_track}",
            "-vn",
            "-ar", str(sample_rate),
            "-ac", str(channels),
        ]
        
        if filters:
            cmd.extend(["-af", ",".join(filters)])
        
        cmd.append(output_path)
        
        return await self._run_ffmpeg(cmd, input_path, progress_callback)
    
    async def render_clip(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float,
        filters: List[str],
        ass_path: Optional[str] = None,
        use_nvenc: bool = True,
        crf: int = 23,
        width: int = 1080,
        height: int = 1920,
        fps: int = 30,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """Render a clip with filters and captions."""
        # Build filter complex
        filter_chain = filters.copy()
        
        # Add ASS subtitles if provided
        if ass_path and self.has_libass:
            # Escape path for filter
            escaped_path = ass_path.replace("\\", "/").replace(":", "\\:")
            filter_chain.append(f"ass='{escaped_path}'")
        
        # Final scale to output size
        filter_chain.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
        filter_chain.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
        filter_chain.append(f"fps={fps}")
        
        # Choose encoder
        encoder = "libx264"
        encoder_opts = ["-preset", "medium", "-crf", str(crf)]
        
        if use_nvenc and self.has_nvenc and not settings.FORCE_CPU:
            encoder = "h264_nvenc"
            encoder_opts = ["-preset", "p4", "-cq", str(crf), "-b:v", "0"]
        
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(duration),
            "-vf", ",".join(filter_chain),
            "-c:v", encoder,
            *encoder_opts,
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-movflags", "+faststart",
            output_path
        ]
        
        return await self._run_ffmpeg(cmd, input_path, progress_callback, duration)
    
    async def extract_frame(
        self,
        input_path: str,
        output_path: str,
        time: float,
        width: int = 1080,
        height: int = 1920
    ) -> bool:
        """Extract a single frame from video."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-ss", str(time),
            "-i", input_path,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
            "-q:v", "2",
            output_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error("Frame extraction failed: %s", stderr.decode())
            return False
        
        return True
    
    async def _run_ffmpeg(
        self,
        cmd: List[str],
        input_path: str,
        progress_callback: Optional[callable] = None,
        duration: Optional[float] = None,
        timeout_minutes: int = 120  # 2 hours max per video
    ) -> bool:
        """Run FFmpeg command with progress tracking via temp file (Windows-safe)."""
        # Get duration if not provided
        if duration is None and progress_callback:
            try:
                info = await self.get_video_info(input_path)
                duration = info["duration"]
            except Exception:
                duration = None
        
        # Create temp file for progress (Windows-safe approach)
        progress_file = None
        if progress_callback and duration:
            progress_file = Path(tempfile.gettempdir()) / f"ffmpeg_progress_{uuid.uuid4().hex}.txt"
        
        # Build command with progress output to file
        cmd_with_progress = cmd.copy()
        idx = cmd_with_progress.index(self.ffmpeg_path) + 1
        
        if progress_file:
            # Use file:// protocol for Windows compatibility
            progress_url = f"file:{progress_file.as_posix()}"
            cmd_with_progress.insert(idx, "-progress")
            cmd_with_progress.insert(idx + 1, progress_url)
        
        cmd_with_progress.insert(idx + (2 if progress_file else 0), "-nostats")
        
        logger.info("Running FFmpeg: %s", " ".join(cmd_with_progress[:5]) + "...")
        
        # Start process - redirect all output to avoid blocking on full buffers
        # On Windows, pipe buffers can fill up and block FFmpeg
        proc = await asyncio.create_subprocess_exec(
            *cmd_with_progress,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        # Poll progress file while FFmpeg runs
        last_progress = 0.0
        last_progress_time = asyncio.get_event_loop().time()
        stall_timeout = 300  # 5 minutes without progress = stalled
        
        try:
            start_time = asyncio.get_event_loop().time()
            max_runtime = timeout_minutes * 60
            
            while proc.returncode is None:
                current_time = asyncio.get_event_loop().time()
                
                # Check absolute timeout
                if current_time - start_time > max_runtime:
                    logger.error("FFmpeg timeout after %d minutes, killing process", timeout_minutes)
                    proc.kill()
                    await proc.wait()
                    return False
                
                # Check if process finished
                try:
                    await asyncio.wait_for(asyncio.shield(proc.wait()), timeout=1.0)
                except asyncio.TimeoutError:
                    pass  # Still running
                
                # Read progress from file
                if progress_file and progress_file.exists():
                    try:
                        content = progress_file.read_text(encoding="utf-8", errors="ignore")
                        # Find last out_time_ms value
                        for line in reversed(content.split("\n")):
                            if line.startswith("out_time_ms="):
                                try:
                                    current_pos = int(line.split("=")[1]) / 1_000_000
                                    if duration and current_pos > 0:
                                        progress = min(current_pos / duration * 100, 99.0)
                                        if progress > last_progress:
                                            last_progress = progress
                                            last_progress_time = current_time
                                            progress_callback(progress)
                                except (ValueError, IndexError):
                                    pass
                                break
                    except Exception as e:
                        logger.debug("Progress file read error (normal during startup): %s", e)
                
                # Check for stall (no progress in 5 minutes)
                if last_progress > 0 and (current_time - last_progress_time) > stall_timeout:
                    logger.error("FFmpeg stalled at %.1f%%, killing process", last_progress)
                    proc.kill()
                    await proc.wait()
                    return False
                    
        finally:
            # Cleanup progress file
            if progress_file and progress_file.exists():
                try:
                    progress_file.unlink()
                except Exception:
                    pass
        
        # Wait for process to fully complete
        await proc.wait()
        
        if proc.returncode != 0:
            logger.error("FFmpeg failed with exit code %d", proc.returncode)
            return False
        
        # Final 100% callback
        if progress_callback:
            progress_callback(100.0)
        
        return True
    
    def build_composition_filter(
        self,
        facecam_rect: Optional[Dict[str, int]],
        content_rect: Optional[Dict[str, int]],
        output_width: int = 1080,
        output_height: int = 1920,
        facecam_ratio: float = 0.4,
        background_blur: bool = True
    ) -> List[str]:
        """Build FFmpeg filter for vertical composition."""
        filters = []
        
        if facecam_rect and content_rect:
            facecam_height = int(output_height * facecam_ratio)
            content_height = output_height - facecam_height
            
            # Crop and scale facecam
            fc = facecam_rect
            filters.append(
                f"[0:v]crop={fc['width']}:{fc['height']}:{fc['x']}:{fc['y']},"
                f"scale={output_width}:{facecam_height}:force_original_aspect_ratio=decrease,"
                f"pad={output_width}:{facecam_height}:(ow-iw)/2:(oh-ih)/2[facecam]"
            )
            
            # Crop and scale content
            cc = content_rect
            filters.append(
                f"[0:v]crop={cc['width']}:{cc['height']}:{cc['x']}:{cc['y']},"
                f"scale={output_width}:{content_height}:force_original_aspect_ratio=decrease,"
                f"pad={output_width}:{content_height}:(ow-iw)/2:(oh-ih)/2[content]"
            )
            
            # Stack vertically
            filters.append(
                f"[facecam][content]vstack=inputs=2[out]"
            )
        else:
            # Simple scale with optional blur background
            if background_blur:
                filters.append(
                    f"[0:v]split[blur][main];"
                    f"[blur]scale={output_width}:{output_height}:force_original_aspect_ratio=increase,"
                    f"crop={output_width}:{output_height},boxblur=20:20[bg];"
                    f"[main]scale={output_width}:{output_height}:force_original_aspect_ratio=decrease[fg];"
                    f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
                )
            else:
                filters.append(
                    f"scale={output_width}:{output_height}:force_original_aspect_ratio=decrease,"
                    f"pad={output_width}:{output_height}:(ow-iw)/2:(oh-ih)/2:black"
                )
        
        return filters






