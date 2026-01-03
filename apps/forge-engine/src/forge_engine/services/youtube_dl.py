"""YouTube/Twitch download service using yt-dlp."""

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """Information about a video from YouTube/Twitch."""
    
    id: str
    title: str
    description: str
    duration: float  # seconds
    thumbnail_url: Optional[str]
    channel: str
    channel_id: str
    upload_date: str  # YYYYMMDD
    view_count: int
    url: str
    platform: str  # "youtube", "twitch"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "duration": self.duration,
            "thumbnailUrl": self.thumbnail_url,
            "channel": self.channel,
            "channelId": self.channel_id,
            "uploadDate": self.upload_date,
            "viewCount": self.view_count,
            "url": self.url,
            "platform": self.platform,
        }


class YouTubeDLService:
    """Service for downloading videos from YouTube and Twitch using yt-dlp."""
    
    _instance: Optional["YouTubeDLService"] = None
    
    def __init__(self):
        self.downloads_dir = settings.LIBRARY_PATH / "downloads"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self._yt_dlp_path = self._find_yt_dlp()
    
    @classmethod
    def get_instance(cls) -> "YouTubeDLService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _find_yt_dlp(self) -> str:
        """Find yt-dlp executable."""
        # Try in venv
        venv_path = Path(__file__).parent.parent.parent.parent / ".venv" / "Scripts" / "yt-dlp.exe"
        if venv_path.exists():
            return str(venv_path)
        
        # Try system PATH
        return "yt-dlp"
    
    @staticmethod
    def detect_platform(url: str) -> Optional[str]:
        """Detect platform from URL."""
        url_lower = url.lower()
        
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "twitch.tv" in url_lower:
            return "twitch"
        
        return None
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if URL is a valid YouTube or Twitch URL."""
        patterns = [
            r"(youtube\.com/watch\?v=[\w-]+)",
            r"(youtu\.be/[\w-]+)",
            r"(youtube\.com/shorts/[\w-]+)",
            r"(twitch\.tv/videos/\d+)",
            r"(clips\.twitch\.tv/[\w-]+)",
            r"(twitch\.tv/[\w]+/clip/[\w-]+)",
        ]
        
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    async def get_video_info(self, url: str) -> Optional[VideoInfo]:
        """Get video information without downloading."""
        platform = self.detect_platform(url)
        if not platform:
            logger.error("Unknown platform for URL: %s", url)
            return None
        
        cmd = [
            self._yt_dlp_path,
            "--dump-json",
            "--no-download",
            "--no-warnings",
            url
        ]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.error("yt-dlp info failed: %s", stderr.decode()[:500])
                return None
            
            data = json.loads(stdout.decode())
            
            return VideoInfo(
                id=data.get("id", ""),
                title=data.get("title", "Sans titre"),
                description=data.get("description", "")[:500] if data.get("description") else "",
                duration=float(data.get("duration", 0)),
                thumbnail_url=data.get("thumbnail"),
                channel=data.get("uploader", data.get("channel", "")),
                channel_id=data.get("uploader_id", data.get("channel_id", "")),
                upload_date=data.get("upload_date", ""),
                view_count=int(data.get("view_count", 0)),
                url=url,
                platform=platform,
            )
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse yt-dlp output: %s", e)
            return None
        except Exception as e:
            logger.exception("Error getting video info: %s", e)
            return None
    
    async def download_video(
        self,
        url: str,
        output_dir: Optional[Path] = None,
        quality: str = "best",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Optional[Path]:
        """Download video from URL.
        
        Args:
            url: YouTube or Twitch URL
            output_dir: Directory to save video (default: downloads_dir)
            quality: Video quality - "best", "1080", "720", "480"
            progress_callback: Callback with (progress_percent, status_message)
            
        Returns:
            Path to downloaded file, or None on failure
        """
        output_dir = output_dir or self.downloads_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Build quality format
        format_spec = self._build_format(quality)
        
        # Output template
        output_template = str(output_dir / "%(title)s [%(id)s].%(ext)s")
        
        cmd = [
            self._yt_dlp_path,
            "-f", format_spec,
            "-o", output_template,
            "--no-warnings",
            "--newline",  # Progress on new lines
            "--progress-template", "%(progress._percent_str)s",
            url
        ]
        
        logger.info("Starting download: %s", url)
        if progress_callback:
            progress_callback(0, "Démarrage du téléchargement...")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Read progress from stdout
            downloaded_file = None
            
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode().strip()
                
                # Parse progress percentage
                if "%" in line_str:
                    try:
                        pct = float(line_str.replace("%", "").strip())
                        if progress_callback:
                            progress_callback(pct, f"Téléchargement: {pct:.0f}%")
                    except ValueError:
                        pass
                
                # Try to find destination file
                if "[download] Destination:" in line_str:
                    downloaded_file = line_str.split("Destination:")[-1].strip()
                elif "has already been downloaded" in line_str:
                    # Already downloaded - extract path
                    match = re.search(r"\[download\] (.+?) has already", line_str)
                    if match:
                        downloaded_file = match.group(1)
            
            await proc.wait()
            
            if proc.returncode != 0:
                stderr = await proc.stderr.read()
                logger.error("Download failed: %s", stderr.decode()[:500])
                if progress_callback:
                    progress_callback(0, "Échec du téléchargement")
                return None
            
            # Find the downloaded file if not captured
            if not downloaded_file:
                # List files in output directory sorted by modification time
                files = list(output_dir.glob("*.*"))
                if files:
                    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    downloaded_file = str(files[0])
            
            if downloaded_file and os.path.exists(downloaded_file):
                logger.info("Download complete: %s", downloaded_file)
                if progress_callback:
                    progress_callback(100, "Téléchargement terminé")
                return Path(downloaded_file)
            
            logger.error("Could not find downloaded file")
            return None
            
        except Exception as e:
            logger.exception("Download error: %s", e)
            if progress_callback:
                progress_callback(0, f"Erreur: {e}")
            return None
    
    def _build_format(self, quality: str) -> str:
        """Build yt-dlp format string."""
        if quality == "best":
            return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        elif quality == "1080":
            return "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best"
        elif quality == "720":
            return "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best"
        elif quality == "480":
            return "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best"
        else:
            return "best"
    
    async def download_thumbnail(self, url: str, output_path: Path) -> bool:
        """Download video thumbnail."""
        info = await self.get_video_info(url)
        if not info or not info.thumbnail_url:
            return False
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(info.thumbnail_url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        output_path.write_bytes(content)
                        return True
        except Exception as e:
            logger.error("Failed to download thumbnail: %s", e)
        
        return False
    
    async def get_channel_videos(
        self,
        channel_url: str,
        limit: int = 10
    ) -> list[VideoInfo]:
        """Get recent videos from a channel."""
        cmd = [
            self._yt_dlp_path,
            "--dump-json",
            "--no-download",
            "--no-warnings",
            "--flat-playlist",
            "--playlist-items", f"1:{limit}",
            channel_url
        ]
        
        videos = []
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                logger.error("Failed to get channel videos: %s", stderr.decode()[:500])
                return []
            
            # Each line is a JSON object
            for line in stdout.decode().strip().split("\n"):
                if line:
                    try:
                        data = json.loads(line)
                        platform = self.detect_platform(channel_url) or "unknown"
                        
                        videos.append(VideoInfo(
                            id=data.get("id", ""),
                            title=data.get("title", "Sans titre"),
                            description="",
                            duration=float(data.get("duration", 0)) if data.get("duration") else 0,
                            thumbnail_url=data.get("thumbnail"),
                            channel=data.get("uploader", data.get("channel", "")),
                            channel_id=data.get("uploader_id", data.get("channel_id", "")),
                            upload_date=data.get("upload_date", ""),
                            view_count=int(data.get("view_count", 0)) if data.get("view_count") else 0,
                            url=data.get("url", data.get("webpage_url", "")),
                            platform=platform,
                        ))
                    except json.JSONDecodeError:
                        continue
            
            return videos
            
        except Exception as e:
            logger.exception("Error getting channel videos: %s", e)
            return []

