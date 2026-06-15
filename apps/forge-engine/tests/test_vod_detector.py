"""Tests for the yt-dlp based Twitch VOD detector parsing."""

from __future__ import annotations

import json

from forge_engine.services.vod_detector import parse_vods

SAMPLE = "\n".join([
    json.dumps({
        "id": "v2796529250",
        "title": "AFTER STARKKK WAITING ROOM COUPE DU MONDE",
        "url": "https://www.twitch.tv/videos/2796529250",
        "duration": 6980.0,
        "timestamp": None,
        "thumbnail": "https://t/x.jpg",
        "view_count": 28865,
    }),
    json.dumps({"id": "v2795979181", "title": "WAITING ROOM", "duration": 3542.0}),
    "not-json-line",
    "",
    json.dumps({"title": "no id here"}),
])


def test_parse_basic_fields():
    vods = parse_vods(SAMPLE, "etostark__")
    assert len(vods) == 2
    v = vods[0]
    assert v.id == "2796529250"        # leading 'v' stripped
    assert v.title.startswith("AFTER STARKKK")
    assert v.url == "https://www.twitch.tv/videos/2796529250"
    assert v.duration == 6980.0
    assert v.channel == "etostark__"
    assert v.platform == "twitch"
    assert v.view_count == 28865
    assert v.thumbnail_url == "https://t/x.jpg"


def test_parse_url_fallback_and_defaults():
    vods = parse_vods(SAMPLE, "etostark__")
    second = vods[1]
    # No "url" key → reconstructed from id.
    assert second.url == "https://www.twitch.tv/videos/2795979181"
    assert second.view_count == 0
    assert second.published_at is None


def test_parse_skips_garbage_and_idless():
    assert parse_vods("", "x") == []
    assert parse_vods("garbage\n{broken", "x") == []
    # entry without an id is skipped (only 2 valid in SAMPLE)
    assert len(parse_vods(SAMPLE, "x")) == 2


def test_timestamp_becomes_published_at():
    line = json.dumps({"id": "123", "title": "t", "timestamp": 1700000000})
    v = parse_vods(line, "c")[0]
    assert v.published_at is not None
    assert v.published_at.year == 2023
