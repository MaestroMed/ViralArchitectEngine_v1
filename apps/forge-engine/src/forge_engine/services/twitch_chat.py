"""Twitch VOD chat as a virality signal.

Chat velocity + emote bursts are the strongest documented real-world predictor
of a clip-worthy stream moment — and the engine had no chat signal at all. We
pull a VOD's chat replay via Twitch's public GQL (read-only, the same persisted
query the web player uses), bin it into a per-window intensity timeline, and
flag spikes via a rolling z-score. The scorer fuses this with audio: "chat
spikes AND voice loud" is the canonical funny-moment marker for stream clips.

No API key / OAuth needed (chat replay is public) and no new dependency (httpx).
"""

from __future__ import annotations

import asyncio
import logging
import re
import statistics
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

GQL_URL = "https://gql.twitch.tv/gql"
# Public web client-id the Twitch player uses for unauthenticated GQL reads.
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
# Persisted-query hash for VideoCommentsByOffsetOrCursor (stable web-player query).
COMMENTS_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"

# Laugh / hype tokens that arrive as plain TEXT — BTTV/FFZ emotes (OMEGALUL,
# KEKW, ...) are not native Twitch emote fragments, and FR LoL chat leans on
# "mdr"/"ptdr" heavily. Native Twitch emotes are counted separately as `emotes`.
LAUGH_TOKENS = re.compile(
    r"(omegalul|kekw|\blul\b|\blmao\b|\bmdr+\b|\bptdr+\b|ahah+|haha+|\bjpp\b|xpdt|xptdr)", re.I
)
HYPE_TOKENS = re.compile(
    r"(\bpog+\b|poggers|pogchamp|let'?s? ?go|\bgg\b|insane|propre|\bwp\b|sheesh|\bclap\b|monka\w*|pepege)", re.I
)


def extract_video_id(meta: dict[str, Any] | None, url: str | None = None) -> str | None:
    """Pull a Twitch VOD numeric id from project meta / import URL."""
    for cand in (
        str((meta or {}).get("detectedVodId") or ""),
        str((meta or {}).get("importUrl") or ""),
        url or "",
    ):
        m = re.search(r"(\d{8,})", cand)
        if m:
            return m.group(1)
    return None


async def fetch_vod_chat(
    video_id: str | int,
    *,
    duration: float | None = None,
    max_requests: int = 4000,
    politeness: float = 0.0,
    on_progress: Callable[[float], None] | None = None,
) -> list[dict[str, Any]]:
    """Fetch a VOD's chat replay by walking ``contentOffsetSeconds``.

    Twitch now gates CURSOR pagination behind an integrity token (anti-scrape),
    but offset paging is still open: each request returns ~one minute of chat
    around the offset, so we step forward by the furthest message seen and
    de-dupe by message id (windows overlap, and dense bursts self-throttle into
    smaller steps). Returns ``{"offset","text","emotes","laughs","hype"}`` per
    message. Graceful: returns whatever it collected on any error, never raises.
    """
    messages: list[dict[str, Any]] = []
    seen: set[str] = set()
    headers = {"Client-ID": CLIENT_ID, "Content-Type": "application/json"}
    offset = 0  # integer stream-seconds; must stay strictly monotonic
    no_new = 0
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            hit_cap = True
            for _req in range(max_requests):
                body = [{
                    "operationName": "VideoCommentsByOffsetOrCursor",
                    # contentOffsetSeconds must be an Int — a float yields an empty page.
                    "variables": {"videoID": str(video_id), "contentOffsetSeconds": int(offset)},
                    "extensions": {"persistedQuery": {"version": 1, "sha256Hash": COMMENTS_HASH}},
                }]
                resp = await client.post(GQL_URL, headers=headers, json=body)
                if resp.status_code != 200:
                    logger.warning("Twitch chat GQL HTTP %s at offset %.0fs", resp.status_code, offset)
                    hit_cap = False
                    break
                node = (resp.json()[0].get("data") or {}).get("video") or {}
                comments = node.get("comments") if node else None
                edges = (comments or {}).get("edges", []) or []
                if not edges:
                    hit_cap = False
                    break

                page_max = offset
                new = 0
                for e in edges:
                    n = e.get("node", {}) or {}
                    mid = n.get("id") or f"{n.get('contentOffsetSeconds')}-{id(e)}"
                    off = float(n.get("contentOffsetSeconds", 0) or 0)
                    page_max = max(page_max, off)
                    if mid in seen:
                        continue
                    seen.add(mid)
                    new += 1
                    frags = (n.get("message", {}) or {}).get("fragments", []) or []
                    text = "".join(f.get("text", "") or "" for f in frags)
                    messages.append({
                        "offset": off,
                        "text": text,
                        "emotes": sum(1 for f in frags if f.get("emote")),
                        "laughs": len(LAUGH_TOKENS.findall(text)),
                        "hype": len(HYPE_TOKENS.findall(text)),
                    })

                if on_progress:
                    on_progress(page_max)
                # Advance strictly forward (integer seconds). Past the furthest
                # message; if a hyper-dense window pinned page_max, inch +1s (we
                # keep the burst already captured); on an empty stretch, skip +30s.
                advance_to = int(page_max) + 1
                if advance_to <= offset:
                    advance_to = offset + (1 if new else 30)
                offset = advance_to
                no_new = no_new + 1 if new == 0 else 0
                if duration and offset >= duration:
                    hit_cap = False
                    break
                if no_new >= 3:
                    hit_cap = False  # 3 pages with nothing new → end of replay
                    break
                if politeness:
                    await asyncio.sleep(politeness)
            if hit_cap:
                logger.warning(
                    "Twitch chat fetch hit max_requests=%d — chat TRUNCATED at offset %.0fs",
                    max_requests, offset,
                )
    except Exception as e:  # noqa: BLE001 — chat is best-effort, never fatal
        logger.warning("Twitch chat fetch failed after %d msgs: %s", len(messages), e)
    messages.sort(key=lambda m: m["offset"])
    return messages


def build_chat_intensity(
    messages: list[dict[str, Any]],
    duration: float,
    *,
    bin_seconds: float = 3.0,
    spike_z: float = 2.0,
) -> dict[str, Any]:
    """Bin chat into a per-window intensity timeline + spikes (rolling z-score).

    A spike is a window whose message count is ``spike_z`` std above the VOD
    mean AND above a small floor (so a dead stream's noise isn't a "spike").
    Each spike is tagged ``laugh`` or ``hype`` by which token kind dominated.
    """
    if not messages or duration <= 0:
        return {"timeline": [], "spikes": [], "total_messages": len(messages)}

    nbins = int(duration // bin_seconds) + 1
    counts = [0] * nbins
    emote = [0] * nbins
    laugh = [0] * nbins
    hype = [0] * nbins
    for m in messages:
        b = int(m["offset"] // bin_seconds)
        if 0 <= b < nbins:
            counts[b] += 1
            emote[b] += m["emotes"]
            laugh[b] += m["laughs"]
            hype[b] += m["hype"]

    mean = statistics.fmean(counts)
    std = statistics.pstdev(counts) or 1.0
    floor = max(3.0, mean)

    timeline: list[dict[str, Any]] = []
    spikes: list[dict[str, Any]] = []
    for i, c in enumerate(counts):
        z = (c - mean) / std
        t = i * bin_seconds
        timeline.append({
            "time": t,
            "msgRate": round(c / bin_seconds, 3),
            "emoteRate": round(emote[i] / bin_seconds, 3),
            "intensity": round(z, 2),
        })
        if z >= spike_z and c >= floor:
            kind = "laugh" if laugh[i] > 0 and laugh[i] >= hype[i] else "hype"
            spikes.append({
                "time": t,
                "end": t + bin_seconds,
                "intensity": round(z, 2),
                "kind": kind,
                "messages": c,
                "laughs": laugh[i],
                "hype": hype[i],
            })

    return {
        "timeline": timeline,
        "spikes": spikes,
        "total_messages": len(messages),
        "mean_rate": round(mean / bin_seconds, 3),
        "peak_z": round(max((s["intensity"] for s in spikes), default=0.0), 2),
        "bin_seconds": bin_seconds,
    }
