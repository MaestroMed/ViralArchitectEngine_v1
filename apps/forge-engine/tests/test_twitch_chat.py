"""Twitch chat signal — id extraction + intensity/spike math (no network)."""

from __future__ import annotations

from forge_engine.services.twitch_chat import build_chat_intensity, extract_video_id
from forge_engine.services.virality import ViralityScorer


def _seg(**kw):
    base = {
        "start_time": 0.0, "end_time": 30.0, "duration": 30.0,
        "transcript": "moment neutre", "transcript_segments": [],
    }
    base.update(kw)
    return base


def test_extract_video_id():
    assert extract_video_id({"detectedVodId": "2798116116"}) == "2798116116"
    assert extract_video_id({"importUrl": "https://www.twitch.tv/videos/2798116116"}) == "2798116116"
    assert extract_video_id({}, "https://twitch.tv/videos/12345678") == "12345678"
    assert extract_video_id({}) is None


def test_intensity_flags_a_laugh_burst():
    # Baseline ~1 msg per 3s bin, then a 20-message laugh burst in one bin.
    msgs = [
        {"offset": float(t), "text": "ok", "emotes": 0, "laughs": 0, "hype": 0}
        for t in range(0, 120, 3)
    ]
    msgs += [
        {"offset": 30.0, "text": "OMEGALUL", "emotes": 0, "laughs": 1, "hype": 0}
        for _ in range(20)
    ]
    out = build_chat_intensity(msgs, duration=120, bin_seconds=3.0)

    assert out["total_messages"] == len(msgs)
    assert out["spikes"], "the burst should register as a spike"
    sp = out["spikes"][0]
    assert abs(sp["time"] - 30.0) < 3.0
    assert sp["kind"] == "laugh"
    assert sp["intensity"] >= 2.0


def test_hype_burst_tagged_hype():
    msgs = [
        {"offset": float(t), "text": "ok", "emotes": 0, "laughs": 0, "hype": 0}
        for t in range(0, 120, 3)
    ]
    msgs += [
        {"offset": 60.0, "text": "POG insane GG", "emotes": 1, "laughs": 0, "hype": 3}
        for _ in range(15)
    ]
    out = build_chat_intensity(msgs, duration=120, bin_seconds=3.0)
    assert any(s["kind"] == "hype" and abs(s["time"] - 60.0) < 3.0 for s in out["spikes"])


def test_intensity_empty_and_zero_duration_safe():
    assert build_chat_intensity([], duration=100)["spikes"] == []
    one = [{"offset": 1.0, "text": "x", "emotes": 0, "laughs": 0, "hype": 0}]
    assert build_chat_intensity(one, duration=0)["spikes"] == []


# ── Scorer integration ────────────────────────────────────────────────────────


def test_chat_hype_spike_boosts_tension():
    s = ViralityScorer()
    base = s._score_segment(_seg(), chat_data=None)
    hot = s._score_segment(_seg(), chat_data={"spikes": [{"time": 10.0, "intensity": 4.0, "kind": "hype"}]})
    assert hot["tension_surprise"] > base["tension_surprise"]
    assert "chat_spike" in hot["tags"]


def test_chat_laugh_spike_boosts_humour():
    s = ViralityScorer()
    base = s._score_segment(_seg(), chat_data=None)
    hot = s._score_segment(_seg(), chat_data={"spikes": [{"time": 10.0, "intensity": 3.0, "kind": "laugh"}]})
    assert hot["humour_reaction"] > base["humour_reaction"]
    assert "chat_laugh" in hot["tags"]


def test_chat_plus_audio_dual_gate_combo():
    s = ViralityScorer()
    chat_only = s._score_segment(_seg(), chat_data={"spikes": [{"time": 10.0, "intensity": 3.0, "kind": "hype"}]})
    combo = s._score_segment(
        _seg(),
        audio_data={"events": [{"type": "scream", "start": 10.0, "end": 11.0, "confidence": 0.8, "viral_score": 0.64}]},
        chat_data={"spikes": [{"time": 10.0, "intensity": 3.0, "kind": "hype"}]},
    )
    assert combo["tension_surprise"] > chat_only["tension_surprise"]
    assert any("combo" in r.lower() for r in combo["reasons"])


def test_chat_spike_outside_window_ignored():
    s = ViralityScorer()
    base = s._score_segment(_seg(), chat_data=None)
    far = s._score_segment(_seg(), chat_data={"spikes": [{"time": 200.0, "intensity": 5.0, "kind": "hype"}]})
    assert far["tension_surprise"] == base["tension_surprise"]
    assert "chat_spike" not in far["tags"]
