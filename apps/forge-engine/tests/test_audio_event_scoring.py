"""Audio path: serialization fix + event-driven scoring.

Two regressions in one: (1) AudioAnalysisResult is a dataclass, so
json.dump silently emptied audio_analysis.json and the scorer got audio_data=None
(no audio signal AT ALL — not even RMS variance); to_dict() fixes that. (2) Even
with audio present, the laughter/cheer/scream EVENT detectors were never read by
the scorer — now they lift humour/tension.
"""

from __future__ import annotations

import json

from forge_engine.services.audio_analysis import (
    AudioAnalysisResult,
    AudioEvent,
    AudioEventType,
)
from forge_engine.services.virality import ViralityScorer


def _seg(transcript="rien de special ici", **kw):
    base = {
        "start_time": 0.0,
        "end_time": 30.0,
        "duration": 30.0,
        "transcript": transcript,
        "transcript_segments": [],
    }
    base.update(kw)
    return base


def test_audio_result_is_json_serializable():
    ev = AudioEvent(
        event_type=AudioEventType.LAUGHTER,
        start_time=5.0, end_time=6.0, confidence=0.9, viral_score=0.85,
    )
    res = AudioAnalysisResult(
        duration=10.0, energy_timeline=[{"time": 1, "value": 0.3}], peaks=[],
        silences=[], events=[ev], average_energy=0.1, energy_variance=0.2,
    )
    d = res.to_dict()
    json.dumps(d)  # the bug: this used to raise TypeError on the raw dataclass
    assert d["events"][0]["type"] == "laughter"
    assert d["events"][0]["start"] == 5.0
    assert d["events"][0]["viral_score"] == 0.85
    assert d["energy_timeline"] == [{"time": 1, "value": 0.3}]


def test_laughter_event_boosts_humour():
    scorer = ViralityScorer()
    base = scorer._score_segment(_seg(), audio_data=None)
    boosted = scorer._score_segment(
        _seg(),
        audio_data={"events": [
            {"type": "laughter", "start": 10.0, "end": 11.0, "confidence": 0.9, "viral_score": 0.85}
        ]},
    )
    assert boosted["humour_reaction"] > base["humour_reaction"]
    assert "audio_reaction" in boosted["tags"]


def test_scream_event_boosts_tension():
    scorer = ViralityScorer()
    base = scorer._score_segment(_seg("calme plat"), audio_data=None)
    spike = scorer._score_segment(
        _seg("calme plat"),
        audio_data={"events": [
            {"type": "scream", "start": 5.0, "end": 6.0, "confidence": 0.8, "viral_score": 0.64}
        ]},
    )
    assert spike["tension_surprise"] > base["tension_surprise"]


def test_event_outside_segment_window_is_ignored():
    scorer = ViralityScorer()
    base = scorer._score_segment(_seg(), audio_data=None)
    far = scorer._score_segment(
        _seg(),
        audio_data={"events": [
            {"type": "laughter", "start": 100.0, "end": 101.0, "confidence": 0.9, "viral_score": 0.85}
        ]},
    )
    assert far["humour_reaction"] == base["humour_reaction"]
    assert "audio_reaction" not in far["tags"]


def test_humour_event_boost_respects_15_cap():
    scorer = ViralityScorer()
    # A transcript already rich in humour markers + a max-strength laugh must
    # not push humour_reaction past its 15 ceiling.
    seg = _seg("mdr c'est trop drole ce moment, j'explose de rire ptdr lol")
    boosted = scorer._score_segment(
        seg,
        audio_data={"events": [
            {"type": "laughter", "start": 1.0, "end": 2.0, "confidence": 1.0, "viral_score": 1.0}
        ]},
    )
    assert boosted["humour_reaction"] <= 15
