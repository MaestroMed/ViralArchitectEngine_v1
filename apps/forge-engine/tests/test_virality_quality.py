"""V2 quality boosters for the virality scorer.

These tests pin the behaviour of each individual booster (duration, filler,
lead-silence, combo) AND the integrated pipeline through ViralityScorer so a
regression in any axis is caught.
"""

from __future__ import annotations

import pytest

from forge_engine.services.virality import ViralityScorer
from forge_engine.services.virality_quality import (
    apply_quality_boosters,
    combo_bonus,
    detect_lead_silence,
    duration_bonus,
    filler_penalty,
    quality_v2_enabled,
)


# ─── Feature flag ────────────────────────────────────────────────────────────

def test_feature_flag_on_by_default(monkeypatch):
    monkeypatch.delenv("FORGE_VIRALITY_QUALITY_V2", raising=False)
    assert quality_v2_enabled() is True


def test_feature_flag_can_be_disabled(monkeypatch):
    monkeypatch.setenv("FORGE_VIRALITY_QUALITY_V2", "0")
    assert quality_v2_enabled() is False


# ─── Duration recalibration ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("duration", "expected_delta", "kind"),
    [
        (25, 5, "optimal"),       # 20-45s sweet spot
        (44, 5, "optimal"),
        (15, 3, "good"),          # 12-60s good band
        (55, 3, "good"),
        (8, 0, "neither"),        # too short to score
        (60.1, 0, "edge"),        # just over good band but under penalty
        (80, -2, "too long"),     # over penalty threshold
    ],
)
def test_duration_bonus(duration, expected_delta, kind):
    """Confirm the recalibrated bands match the TikTok 2026 completion-rate
    optimisation: 20-45s big bonus, 12-60s moderate, >75s penalised."""
    b = duration_bonus(duration)
    assert b.delta == expected_delta, kind


# ─── Filler penalty ──────────────────────────────────────────────────────────

def test_filler_penalty_clean_speech():
    transcript = "Salut tout le monde, on lance ce stream tranquille. Allez, on y va!"
    delta, _ = filler_penalty(transcript)
    assert delta == 0


def test_filler_penalty_moderate():
    """One sentence, two fillers → ratio 2/1 == 2.0, heavy."""
    transcript = "Euh donc voilà euh comment dire."
    delta, reason = filler_penalty(transcript)
    assert delta == -4
    assert reason is not None


def test_filler_penalty_handles_empty():
    assert filler_penalty("") == (0, None)
    assert filler_penalty("    ") == (0, None)


# ─── Lead silence ────────────────────────────────────────────────────────────

def test_lead_silence_detects_gap():
    segments = [{"start": 5.5, "end": 7.0, "text": "hey"}]
    recommended, reason = detect_lead_silence(segment_start=2.0, transcript_segments=segments)
    assert recommended is not None
    assert recommended == pytest.approx(5.3, abs=0.01)
    assert "silence" in reason.lower()


def test_lead_silence_skips_tight_gap():
    segments = [{"start": 0.3, "end": 1.0, "text": "hey"}]
    assert detect_lead_silence(0.0, segments) == (None, None)


def test_lead_silence_handles_missing_data():
    assert detect_lead_silence(0.0, None) == (None, None)
    assert detect_lead_silence(0.0, []) == (None, None)
    assert detect_lead_silence(0.0, [{"text": "hi"}]) == (None, None)  # no "start"


# ─── Combo bonus ─────────────────────────────────────────────────────────────

def test_combo_hook_humour():
    score = {"hook_strength": 14, "humour_reaction": 10, "tension_surprise": 0, "payoff": 0}
    delta, reason = combo_bonus(score)
    assert delta == 3
    assert "hook" in reason.lower() and "humour" in reason.lower()


def test_combo_surprise_payoff():
    score = {"hook_strength": 0, "humour_reaction": 0, "tension_surprise": 12, "payoff": 15}
    delta, reason = combo_bonus(score)
    assert delta == 3
    assert "surprise" in reason.lower()


def test_combo_no_match():
    score = {"hook_strength": 10, "humour_reaction": 5, "tension_surprise": 3, "payoff": 5}
    assert combo_bonus(score) == (0, None)


# ─── Integrated: apply_quality_boosters ──────────────────────────────────────

def test_apply_idempotent():
    score = {
        "hook_strength": 14, "payoff": 8, "humour_reaction": 8, "tension_surprise": 0,
        "clarity_autonomy": 10, "rhythm": 5, "total": 45, "reasons": [], "tags": [],
    }
    segment = {"transcript": "hello", "duration": 30, "start_time": 0}
    apply_quality_boosters(score, segment)
    payoff_after_first = score["payoff"]
    apply_quality_boosters(score, segment)
    assert score["payoff"] == payoff_after_first  # no double-application


def test_apply_off_when_flag_disabled(monkeypatch):
    monkeypatch.setenv("FORGE_VIRALITY_QUALITY_V2", "0")
    score = {
        "hook_strength": 5, "payoff": 3, "humour_reaction": 0, "tension_surprise": 0,
        "clarity_autonomy": 10, "rhythm": 5, "total": 23, "reasons": [], "tags": [],
    }
    snapshot = dict(score)
    apply_quality_boosters(score, {"transcript": "x", "duration": 30, "start_time": 0})
    assert {k: score[k] for k in snapshot} == snapshot


def test_apply_subtracts_legacy_duration_then_re_adds():
    """The base scorer already gave +5 for 45-90s. V2 must subtract that
    BEFORE giving its own (smaller) bonus, otherwise we'd double-count."""
    score = {
        "hook_strength": 0, "payoff": 5, "humour_reaction": 0, "tension_surprise": 0,
        "clarity_autonomy": 10, "rhythm": 5, "total": 20,
        "reasons": ["Optimal duration (45-90s)"], "tags": [],
    }
    apply_quality_boosters(score, {"transcript": "x", "duration": 55, "start_time": 0})
    # 55s is in the new "good" band → +3, legacy +5 was subtracted, so 5−5+3 = 3.
    assert score["payoff"] == 3
    # The legacy reason has been dropped.
    assert not any("45-90" in r for r in score["reasons"])


# ─── Integrated: end-to-end through ViralityScorer ───────────────────────────

def _make_segment(*, duration: float, transcript: str, transcript_segs: list[dict] | None = None,
                  start_time: float = 0.0) -> dict:
    return {
        "start_time": start_time,
        "end_time": start_time + duration,
        "duration": duration,
        "transcript": transcript,
        "transcript_segments": transcript_segs or [],
    }


def test_v2_scorer_rewards_short_clip_over_long_one():
    """At equal content quality, the 30s clip should now outscore the 80s clip
    on payoff (TikTok 2026 completion rate)."""
    short = _make_segment(
        duration=30,
        transcript="C'est INCROYABLE attends regarde, mdr je suis mort de rire!",
    )
    long_ = _make_segment(
        duration=80,
        transcript="C'est INCROYABLE attends regarde, mdr je suis mort de rire!",
    )
    scorer = ViralityScorer(use_llm=False)
    short_score = scorer._score_segment(short)
    long_score = scorer._score_segment(long_)
    assert short_score["payoff"] > long_score["payoff"]
    assert short_score["total"] > long_score["total"]


def test_v2_scorer_penalises_filler_heavy_transcript():
    clean = _make_segment(duration=30, transcript="Allez, on y va, c'est parti!")
    filler = _make_segment(
        duration=30,
        transcript="Euh... donc voilà euh comment dire, tu vois, euh j'sais pas euh.",
    )
    scorer = ViralityScorer(use_llm=False)
    assert scorer._score_segment(clean)["clarity_autonomy"] > scorer._score_segment(filler)["clarity_autonomy"]


def test_v2_scorer_emits_recommended_start_on_lead_silence():
    segment = _make_segment(
        duration=30,
        start_time=10.0,
        transcript="C'est parti, ça va être chaud!",
        transcript_segs=[{"start": 14.0, "end": 14.5, "text": "C'est"}],
    )
    scorer = ViralityScorer(use_llm=False)
    score = scorer._score_segment(segment)
    assert "recommended_start" in score
    assert score["recommended_start"] == pytest.approx(13.8, abs=0.05)
