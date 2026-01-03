"""Playwright-based web scraper for Twitch/YouTube channel monitoring.

NOTE: This is for READ-ONLY scraping to detect new VODs.
DO NOT use for automated uploads - risk of account bans.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ChannelInfo:
    """Channel information."""
    
    id: str
    name: str
    display_name: str
    platform: str  # "twitch" or "youtube"
    profile_image_url: Optional[str] = None
    is_live: bool = False
    followers: int = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "displayName": self.display_name,
            "platform": self.platform,
            "profileImageUrl": self.profile_image_url,
            "isLive": self.is_live,
            "followers": self.followers,
        }


@dataclass
class VODInfo:
    """VOD/Video information from scraping."""
    
    id: str
    title: str
    channel: str
    platform: str
    url: str
    thumbnail_url: Optional[str]
    duration: float  # seconds
    published_at: Optional[datetime]
    view_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "channel": self.channel,
            "platform": self.platform,
            "url": self.url,
            "thumbnailUrl": self.thumbnail_url,
            "duration": self.duration,
            "publishedAt": self.published_at.isoformat() if self.published_at else None,
            "viewCount": self.view_count,
        }


class PlaywrightScraper:
    """Headless browser scraper for Twitch/YouTube channel monitoring."""
    
    _instance: Optional["PlaywrightScraper"] = None
    _browser = None
    _playwright = None
    
    def __init__(self):
        self._initialized = False
        self._rate_limit_delay = 5.0  # seconds between requests
        self._last_request_time = 0.0
    
    @classmethod
    def get_instance(cls) -> "PlaywrightScraper":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self._browser is not None:
            return
        
        try:
            from playwright.async_api import async_playwright
            
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )
            self._initialized = True
            logger.info("Playwright browser initialized")
        except Exception as e:
            logger.error("Failed to initialize Playwright: %s", e)
            raise
    
    async def _rate_limit(self):
        """Apply rate limiting."""
        import time
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()
    
    async def close(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._initialized = False
        logger.info("Playwright browser closed")
    
    async def get_twitch_channel_info(self, channel_name: str) -> Optional[ChannelInfo]:
        """Get Twitch channel information."""
        await self._ensure_browser()
        await self._rate_limit()
        
        context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            url = f"https://www.twitch.tv/{channel_name}"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)  # Wait for dynamic content
            
            # Check if channel exists
            if "Error" in await page.title() or "404" in await page.title():
                return None
            
            # Get channel info from page
            display_name = channel_name
            is_live = False
            
            # Try to get display name
            try:
                display_name_el = await page.query_selector("h1[data-a-target='stream-title']")
                if display_name_el:
                    display_name = await display_name_el.inner_text()
            except Exception:
                pass
            
            # Check if live
            try:
                live_indicator = await page.query_selector("[data-a-target='live-indicator']")
                is_live = live_indicator is not None
            except Exception:
                pass
            
            # Get profile image
            profile_image = None
            try:
                img_el = await page.query_selector("img[alt*='avatar'], img.channel-header__avatar")
                if img_el:
                    profile_image = await img_el.get_attribute("src")
            except Exception:
                pass
            
            return ChannelInfo(
                id=channel_name,
                name=channel_name,
                display_name=display_name,
                platform="twitch",
                profile_image_url=profile_image,
                is_live=is_live,
            )
            
        except Exception as e:
            logger.error("Error scraping Twitch channel %s: %s", channel_name, e)
            return None
        finally:
            await page.close()
            await context.close()
    
    async def get_twitch_vods(self, channel_name: str, limit: int = 10) -> list[VODInfo]:
        """Get recent VODs from a Twitch channel."""
        await self._ensure_browser()
        await self._rate_limit()
        
        context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        vods = []
        
        try:
            url = f"https://www.twitch.tv/{channel_name}/videos?filter=archives&sort=time"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)  # Wait for video grid to load
            
            # Find video cards
            video_cards = await page.query_selector_all("[data-a-target='preview-card-image-link'], a.tw-link[href*='/videos/']")
            
            for card in video_cards[:limit]:
                try:
                    href = await card.get_attribute("href")
                    if not href or "/videos/" not in href:
                        continue
                    
                    # Extract video ID
                    video_id_match = re.search(r"/videos/(\d+)", href)
                    if not video_id_match:
                        continue
                    video_id = video_id_match.group(1)
                    
                    # Get title
                    title_el = await card.query_selector("h3, [title]")
                    title = await title_el.inner_text() if title_el else f"VOD {video_id}"
                    
                    # Get thumbnail
                    thumbnail = None
                    img_el = await card.query_selector("img")
                    if img_el:
                        thumbnail = await img_el.get_attribute("src")
                    
                    # Get duration
                    duration = 0
                    duration_el = await card.query_selector(".tw-media-card-stat")
                    if duration_el:
                        duration_text = await duration_el.inner_text()
                        duration = self._parse_duration(duration_text)
                    
                    vods.append(VODInfo(
                        id=video_id,
                        title=title.strip() if title else f"VOD {video_id}",
                        channel=channel_name,
                        platform="twitch",
                        url=f"https://www.twitch.tv/videos/{video_id}",
                        thumbnail_url=thumbnail,
                        duration=duration,
                        published_at=None,  # Would need more scraping
                    ))
                    
                except Exception as e:
                    logger.warning("Error parsing VOD card: %s", e)
                    continue
            
            logger.info("Found %d VODs for %s", len(vods), channel_name)
            return vods
            
        except Exception as e:
            logger.error("Error scraping Twitch VODs for %s: %s", channel_name, e)
            return []
        finally:
            await page.close()
            await context.close()
    
    async def get_youtube_channel_videos(self, channel_url: str, limit: int = 10) -> list[VODInfo]:
        """Get recent videos from a YouTube channel."""
        await self._ensure_browser()
        await self._rate_limit()
        
        context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        videos = []
        
        try:
            # Navigate to channel videos
            if "/videos" not in channel_url:
                channel_url = channel_url.rstrip("/") + "/videos"
            
            await page.goto(channel_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            
            # Find video renderers
            video_els = await page.query_selector_all("ytd-rich-item-renderer, ytd-grid-video-renderer")
            
            for el in video_els[:limit]:
                try:
                    # Get video link
                    link_el = await el.query_selector("a#thumbnail, a.yt-simple-endpoint[href*='watch']")
                    if not link_el:
                        continue
                    
                    href = await link_el.get_attribute("href")
                    if not href or "watch?v=" not in href:
                        continue
                    
                    video_id_match = re.search(r"watch\?v=([^&]+)", href)
                    if not video_id_match:
                        continue
                    video_id = video_id_match.group(1)
                    
                    # Get title
                    title_el = await el.query_selector("#video-title, #video-title-link")
                    title = await title_el.get_attribute("title") if title_el else f"Video {video_id}"
                    
                    # Get thumbnail
                    thumbnail = None
                    img_el = await el.query_selector("img")
                    if img_el:
                        thumbnail = await img_el.get_attribute("src")
                    
                    # Get duration
                    duration = 0
                    duration_el = await el.query_selector("span.ytd-thumbnail-overlay-time-status-renderer")
                    if duration_el:
                        duration_text = await duration_el.inner_text()
                        duration = self._parse_duration(duration_text)
                    
                    # Get channel name from URL
                    channel_name = re.search(r"/@?([^/]+)", channel_url)
                    channel = channel_name.group(1) if channel_name else "Unknown"
                    
                    videos.append(VODInfo(
                        id=video_id,
                        title=title.strip() if title else f"Video {video_id}",
                        channel=channel,
                        platform="youtube",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        thumbnail_url=thumbnail,
                        duration=duration,
                        published_at=None,
                    ))
                    
                except Exception as e:
                    logger.warning("Error parsing YouTube video: %s", e)
                    continue
            
            logger.info("Found %d videos from %s", len(videos), channel_url)
            return videos
            
        except Exception as e:
            logger.error("Error scraping YouTube channel %s: %s", channel_url, e)
            return []
        finally:
            await page.close()
            await context.close()
    
    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string like '2:30:15' or '45:30' to seconds."""
        if not duration_str:
            return 0
        
        duration_str = duration_str.strip()
        parts = duration_str.split(":")
        
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + int(seconds)
            elif len(parts) == 1:
                return int(parts[0])
        except ValueError:
            pass
        
        return 0


# Background task for periodic VOD checking
class ChannelMonitor:
    """Background monitor for watched channels."""
    
    def __init__(self):
        self.watched_channels: dict[str, dict] = {}  # channel_id -> config
        self._running = False
        self._task = None
    
    def add_channel(self, channel_id: str, platform: str, check_interval: int = 3600):
        """Add a channel to monitor.
        
        Args:
            channel_id: Channel name/ID
            platform: "twitch" or "youtube"
            check_interval: Seconds between checks (default 1 hour)
        """
        self.watched_channels[channel_id] = {
            "platform": platform,
            "check_interval": check_interval,
            "last_check": None,
            "last_vods": [],
        }
        logger.info("Added channel to monitor: %s (%s)", channel_id, platform)
    
    def remove_channel(self, channel_id: str):
        """Remove a channel from monitoring."""
        if channel_id in self.watched_channels:
            del self.watched_channels[channel_id]
            logger.info("Removed channel from monitor: %s", channel_id)
    
    async def check_channel(self, channel_id: str) -> list[VODInfo]:
        """Check a channel for new VODs."""
        if channel_id not in self.watched_channels:
            return []
        
        config = self.watched_channels[channel_id]
        scraper = PlaywrightScraper.get_instance()
        
        if config["platform"] == "twitch":
            vods = await scraper.get_twitch_vods(channel_id, limit=5)
        elif config["platform"] == "youtube":
            vods = await scraper.get_youtube_channel_videos(
                f"https://www.youtube.com/@{channel_id}", limit=5
            )
        else:
            return []
        
        # Find new VODs
        old_ids = {v["id"] for v in config.get("last_vods", [])}
        new_vods = [v for v in vods if v.id not in old_ids]
        
        # Update cache
        config["last_check"] = datetime.now()
        config["last_vods"] = [v.to_dict() for v in vods]
        
        return new_vods
    
    async def start(self):
        """Start the background monitoring loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Channel monitor started")
    
    async def stop(self):
        """Stop the background monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Channel monitor stopped")
    
    async def _monitor_loop(self):
        """Background loop to check channels periodically."""
        while self._running:
            for channel_id, config in self.watched_channels.items():
                try:
                    last_check = config.get("last_check")
                    interval = config.get("check_interval", 3600)
                    
                    # Skip if checked recently
                    if last_check and (datetime.now() - last_check).total_seconds() < interval:
                        continue
                    
                    new_vods = await self.check_channel(channel_id)
                    
                    if new_vods:
                        logger.info("New VODs detected for %s: %d", channel_id, len(new_vods))
                        # TODO: Emit WebSocket event for new VODs
                        
                except Exception as e:
                    logger.error("Error checking channel %s: %s", channel_id, e)
            
            # Sleep between checks
            await asyncio.sleep(60)  # Check every minute if any channel needs updating

