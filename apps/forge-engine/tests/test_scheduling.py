"""Timezone + export-window scheduling helpers."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from forge_engine.core import scheduling

# ─── timezone ────────────────────────────────────────────────────────────────

def test_default_timezone(monkeypatch):
    monkeypatch.delenv("FORGE_TIMEZONE", raising=False)
    assert scheduling.get_timezone() == ZoneInfo("Europe/Paris")


def test_custom_timezone(monkeypatch):
    monkeypatch.setenv("FORGE_TIMEZONE", "America/New_York")
    assert scheduling.get_timezone() == ZoneInfo("America/New_York")


def test_invalid_timezone_falls_back(monkeypatch):
    monkeypatch.setenv("FORGE_TIMEZONE", "Mars/Olympus_Mons")
    assert scheduling.get_timezone() == ZoneInfo("Europe/Paris")


def test_now_local_is_aware(monkeypatch):
    monkeypatch.setenv("FORGE_TIMEZONE", "Europe/Paris")
    assert scheduling.now_local().tzinfo is not None


# ─── window parsing ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("05:00-07:00", (time(5, 0), time(7, 0))),
        ("23:30-02:15", (time(23, 30), time(2, 15))),
        (" 6:5 - 7:8 ", (time(6, 5), time(7, 8))),
    ],
)
def test_parse_window_valid(spec, expected):
    assert scheduling.parse_window(spec) == expected


@pytest.mark.parametrize("spec", ["", "   ", "noon", "05:00", "25:00-26:00-x", "a:b-c:d"])
def test_parse_window_invalid(spec):
    # 25:00 is out of range → time() raises → None. Others malformed → None.
    assert scheduling.parse_window(spec) is None


# ─── within-window logic ─────────────────────────────────────────────────────

def test_within_normal_window():
    w = (time(5, 0), time(7, 0))
    assert scheduling.is_within_window(time(6, 0), w) is True
    assert scheduling.is_within_window(time(5, 0), w) is True   # inclusive start
    assert scheduling.is_within_window(time(7, 0), w) is False  # exclusive end
    assert scheduling.is_within_window(time(4, 59), w) is False
    assert scheduling.is_within_window(time(8, 0), w) is False


def test_within_wraparound_window():
    w = (time(23, 0), time(2, 0))
    assert scheduling.is_within_window(time(23, 30), w) is True
    assert scheduling.is_within_window(time(1, 0), w) is True
    assert scheduling.is_within_window(time(2, 0), w) is False
    assert scheduling.is_within_window(time(12, 0), w) is False


# ─── should_export_now ───────────────────────────────────────────────────────

def test_should_export_now_no_window(monkeypatch):
    monkeypatch.delenv("FORGE_EXPORT_WINDOW", raising=False)
    # No restriction → always exportable.
    assert scheduling.should_export_now(datetime(2026, 6, 15, 3, 0)) is True


def test_should_export_now_inside(monkeypatch):
    monkeypatch.setenv("FORGE_EXPORT_WINDOW", "05:00-07:00")
    assert scheduling.should_export_now(datetime(2026, 6, 15, 6, 0)) is True


def test_should_export_now_outside(monkeypatch):
    monkeypatch.setenv("FORGE_EXPORT_WINDOW", "05:00-07:00")
    assert scheduling.should_export_now(datetime(2026, 6, 15, 12, 0)) is False


# ─── seconds_until_window ────────────────────────────────────────────────────

def test_seconds_until_window_inside_is_zero():
    w = (time(5, 0), time(7, 0))
    assert scheduling.seconds_until_window(w, datetime(2026, 6, 15, 6, 0)) == 0


def test_seconds_until_window_later_today():
    w = (time(5, 0), time(7, 0))
    # At 03:00, the 05:00 window opens in 2h.
    assert scheduling.seconds_until_window(w, datetime(2026, 6, 15, 3, 0)) == 2 * 3600


def test_seconds_until_window_tomorrow():
    w = (time(5, 0), time(7, 0))
    # At 12:00, next 05:00 is 17h away.
    assert scheduling.seconds_until_window(w, datetime(2026, 6, 15, 12, 0)) == 17 * 3600
