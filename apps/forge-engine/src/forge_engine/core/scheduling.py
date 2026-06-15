"""Time-window + timezone helpers for the morning automation.

Two needs:
1. The publish scheduler and auto-pipeline hardcoded Europe/Paris. Make the
   timezone configurable (FORGE_TIMEZONE) so the same build works for anyone.
2. "Clips ready by morning": let the auto-pipeline defer the (GPU-heavy) export
   step to a configurable window (FORGE_EXPORT_WINDOW=05:00-07:00) so renders
   happen overnight and the queue is fresh at wake-up instead of trickling in.

All functions here are pure and unit-tested; the services just call them.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Europe/Paris"


def get_timezone() -> ZoneInfo:
    """Resolve FORGE_TIMEZONE (IANA name) → ZoneInfo, falling back to
    Europe/Paris if unset or invalid."""
    name = os.environ.get("FORGE_TIMEZONE", DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        logger.warning("Invalid FORGE_TIMEZONE %r; using %s", name, DEFAULT_TIMEZONE)
        return ZoneInfo(DEFAULT_TIMEZONE)


def now_local() -> datetime:
    """Timezone-aware 'now' in the configured zone."""
    return datetime.now(get_timezone())


def parse_window(spec: str) -> tuple[time, time] | None:
    """Parse 'HH:MM-HH:MM' into (start, end) ``time`` objects.

    Returns None if the spec is empty/malformed (caller treats None as
    "no window restriction"). Wrap-around windows (e.g. 23:00-02:00) are
    allowed and handled by is_within_window.
    """
    if not spec or not spec.strip():
        return None
    try:
        start_s, end_s = spec.strip().split("-", 1)
        sh, sm = (int(x) for x in start_s.strip().split(":"))
        eh, em = (int(x) for x in end_s.strip().split(":"))
        return time(sh, sm), time(eh, em)
    except (ValueError, IndexError):
        logger.warning("Invalid time window %r (expected HH:MM-HH:MM)", spec)
        return None


def is_within_window(now: time, window: tuple[time, time]) -> bool:
    """Is ``now`` inside [start, end)? Handles windows that wrap midnight.

    05:00-07:00 → True only between 5am and 7am.
    23:00-02:00 → True from 11pm through 2am (wrap-around).
    """
    start, end = window
    if start <= end:
        return start <= now < end
    # Wrap-around: inside if after start OR before end.
    return now >= start or now < end


def export_window() -> tuple[time, time] | None:
    """The configured export window, or None when unrestricted."""
    return parse_window(os.environ.get("FORGE_EXPORT_WINDOW", ""))


def should_export_now(now: datetime | None = None) -> bool:
    """True if exports may run right now.

    No window configured → always True (current behaviour, exports run
    immediately after analysis). Window configured → only inside it.
    """
    window = export_window()
    if window is None:
        return True
    current = (now or now_local()).timetz().replace(tzinfo=None)
    return is_within_window(current, window)


def seconds_until_window(window: tuple[time, time], now: datetime | None = None) -> int:
    """Seconds until the next time we enter ``window``. 0 if already inside.

    Used so a deferred export loop can sleep efficiently instead of polling.
    """
    ref = now or now_local()
    current = ref.timetz().replace(tzinfo=None)
    if is_within_window(current, window):
        return 0
    start = window[0]
    today_start = ref.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    if today_start <= ref:
        today_start = today_start + timedelta(days=1)
    return int((today_start - ref).total_seconds())
