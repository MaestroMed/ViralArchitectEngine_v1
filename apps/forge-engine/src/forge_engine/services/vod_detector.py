"""yt-dlp based Twitch VOD detector.

Replaces the Playwright scraper for the auto-pipeline's VOD discovery: yt-dlp is
already a hard dependency (downloads), needs no headless browser, and one
`--flat-playlist --dump-json` call lists a channel's recent archives. Returns the
same `VODInfo` shape the pipeline already consumes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import UTC, datetime

from forge_engine.services.playwright_scraper import VODInfo

logger = logging.getLogger(__name__)


def _yt_dlp_path() -> str:
    return shutil.which("yt-dlp") or "yt-dlp"


def parse_vods(stdout: str, channel_name: str) -> list[VODInfo]:
    """Parse yt-dlp --dump-json (one JSON object per line) into VODInfo list."""
    vods: list[VODInfo] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Twitch VOD ids come through as "v2796529250"; normalize to numeric.
        raw_id = str(entry.get("id") or "").lstrip("vV")
        if not raw_id:
            continue
        ts = entry.get("timestamp")
        published = (
            datetime.fromtimestamp(ts, tz=UTC)
            if isinstance(ts, (int, float))
            else None
        )
        vods.append(
            VODInfo(
                id=raw_id,
                title=entry.get("title") or f"VOD {raw_id}",
                channel=channel_name,
                platform="twitch",
                url=entry.get("url") or entry.get("webpage_url")
                or f"https://www.twitch.tv/videos/{raw_id}",
                thumbnail_url=entry.get("thumbnail"),
                duration=float(entry.get("duration") or 0.0),
                published_at=published,
                view_count=int(entry.get("view_count") or 0),
            )
        )
    return vods


async def get_twitch_vods(channel_name: str, limit: int = 5) -> list[VODInfo]:
    """List a Twitch channel's most recent archive VODs (newest first)."""
    url = f"https://www.twitch.tv/{channel_name}/videos?filter=archives&sort=time"
    cmd = [
        _yt_dlp_path(),
        "--flat-playlist",
        "--ignore-errors",
        "--no-warnings",
        "-I", f"1:{max(1, limit)}",
        "--dump-json",
        url,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
    except FileNotFoundError:
        logger.warning("yt-dlp not found on PATH — cannot detect VODs")
        return []
    if proc.returncode != 0 and not out:
        logger.warning(
            "yt-dlp VOD list failed for %s: %s",
            channel_name, err.decode(errors="replace")[:300],
        )
        return []
    vods = parse_vods(out.decode(errors="replace"), channel_name)
    logger.info("[VODDetector] %s: %d VOD(s) via yt-dlp", channel_name, len(vods))
    return vods
