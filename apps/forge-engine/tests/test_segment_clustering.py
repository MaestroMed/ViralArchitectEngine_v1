"""Tests for _cluster_segments — merging overlapping hot windows into one
variable-length clip per moment (kills redundant near-duplicate 30s clips)."""

from __future__ import annotations

from dataclasses import dataclass

from forge_engine.services.auto_pipeline import _cluster_segments, _select_clips


@dataclass
class FakeSeg:
    start_time: float
    duration: float
    score_total: float
    cold_open_start_time: float | None = None

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


def test_empty():
    assert _cluster_segments([], merge_gap=25, cap=120) == []


def test_three_redundant_windows_merge_into_one():
    # Three 30s windows inside one ~136s exchange → ONE clip, not three.
    segs = [
        FakeSeg(3121, 30, 70),
        FakeSeg(3184, 30, 72),
        FakeSeg(3227, 30, 67),
    ]
    specs = _cluster_segments(segs, merge_gap=40, cap=120)
    assert len(specs) == 1
    s = specs[0]
    assert s["score"] == 72  # best member's score
    assert s["rep"].start_time == 3184  # rep is highest-scoring member
    # union 3121..3257 = 136s, capped to 120
    assert s["duration"] == 120


def test_distant_windows_stay_separate():
    segs = [FakeSeg(100, 30, 65), FakeSeg(900, 30, 64)]
    specs = _cluster_segments(segs, merge_gap=25, cap=120)
    assert len(specs) == 2


def test_variable_durations_preserved_under_cap():
    # A lone 30s window stays 30s; an adjacent pair becomes longer.
    segs = [
        FakeSeg(100, 30, 66),            # lone → 30s
        FakeSeg(500, 30, 64),            # pair with next (gap 10s) → 70s
        FakeSeg(540, 30, 63),
    ]
    specs = _cluster_segments(segs, merge_gap=25, cap=120)
    durs = sorted(s["duration"] for s in specs)
    assert durs == [30, 70]  # 500..570 = 70s


def test_cap_centers_on_punch():
    # One huge cluster, punch near the end → window ends around the punch+.
    segs = [
        FakeSeg(1000, 30, 60),
        FakeSeg(1040, 200, 80, cold_open_start_time=1200),  # long, high score, punch=1200
    ]
    specs = _cluster_segments(segs, merge_gap=25, cap=120, pre=8)
    s = specs[0]
    assert s["duration"] == 120
    # punch 1200 inside; start = punch-pre = 1192, but clamped so cap fits union.
    assert s["start"] <= 1200 <= s["end"]


def test_sorted_by_score_desc():
    segs = [FakeSeg(0, 30, 61), FakeSeg(500, 30, 70), FakeSeg(1000, 30, 65)]
    specs = _cluster_segments(segs, merge_gap=25, cap=120)
    scores = [s["score"] for s in specs]
    assert scores == sorted(scores, reverse=True)


# ── _select_clips (greedy non-overlapping, natural durations) ──────────────

def test_select_keeps_natural_durations():
    # Multi-scale windows over distinct regions → each kept at natural length.
    segs = [
        FakeSeg(100, 84, 72),    # 84s
        FakeSeg(1000, 120, 67),  # 2min
        FakeSeg(2000, 30, 61),   # 30s
    ]
    specs = _select_clips(segs, cap=120, max_clips=10)
    durs = sorted(round(s["duration"]) for s in specs)
    assert durs == [30, 84, 120]


def test_select_dedupes_overlapping_keeps_highest_score():
    # Two windows over the same moment → only the higher score survives.
    segs = [
        FakeSeg(100, 84, 72),    # wins
        FakeSeg(120, 30, 70),    # overlaps the first → dropped
        FakeSeg(900, 40, 65),    # distinct → kept
    ]
    specs = _select_clips(segs, cap=120, max_clips=10)
    starts = sorted(round(s["start"]) for s in specs)
    assert starts == [100, 900]
    assert specs[0]["score"] == 72


def test_select_caps_long_window_around_punch():
    segs = [FakeSeg(1000, 214, 80, cold_open_start_time=1180)]
    specs = _select_clips(segs, cap=120, max_clips=5)
    s = specs[0]
    assert round(s["duration"]) == 120
    assert s["start"] <= 1180 <= s["end"]


def test_select_respects_max_clips():
    segs = [FakeSeg(i * 200, 60, 60 + i) for i in range(10)]
    specs = _select_clips(segs, cap=120, max_clips=3)
    assert len(specs) == 3


def test_select_drops_too_short():
    segs = [FakeSeg(100, 5, 90), FakeSeg(500, 40, 80)]
    specs = _select_clips(segs, cap=120, max_clips=5, min_seconds=12)
    assert len(specs) == 1
    assert round(specs[0]["duration"]) == 40
