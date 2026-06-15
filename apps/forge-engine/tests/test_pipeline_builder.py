"""Filtergraph-construction tests for the single-pass pipeline builder.

These guard the filter-pad rules that have bitten us in production:
  * a filter-pad output may be consumed only ONCE → reuse needs split/asplit;
  * the concat filter (v=1:a=1) needs pads interleaved PER SEGMENT
    (v0,a0,v1,a1,…), not all-videos-then-all-audios.
They assert on the generated filtergraph string (fast, no ffmpeg needed).
"""

from __future__ import annotations

import re
from pathlib import Path

from forge_engine.services.pipeline_builder import PipelineConfig, PipelineSinglePass


def _filter_string(cfg: PipelineConfig) -> str:
    cmd = PipelineSinglePass(cfg).build_command()
    return cmd[cmd.index("-filter_complex") + 1]


def _base(**kw) -> PipelineConfig:
    defaults = dict(
        source_path=Path("/tmp/src.mp4"),
        segment_start=10.0,
        segment_duration=30.0,
        source_width=1920,
        source_height=1080,
    )
    defaults.update(kw)
    return PipelineConfig(**defaults)


def test_two_zone_layout_splits_source_and_vstacks():
    f = _filter_string(_base(
        facecam_rect={"x": 0.7, "y": 0.71, "w": 0.255, "h": 0.29},
        content_rect={"x": 0.04, "y": 0.0, "w": 0.63, "h": 1.0},
        facecam_ratio=0.42,
    ))
    # Source split so each crop reads its own copy (no [0:v] reuse).
    assert "[0:v]split=2[lz_f][lz_c]" in f
    assert "vstack[composed_v]" in f
    # [0:v] appears exactly once as a video consumer (the split).
    assert f.count("[0:v]") == 1


def test_facecam_ratio_sets_top_zone_height():
    # ratio 0.5 of 1920 → 960 top, 960 bottom
    f = _filter_string(_base(
        output_width=1080, output_height=1920,
        facecam_rect={"x": 0.7, "y": 0.7, "w": 0.25, "h": 0.3},
        content_rect={"x": 0.0, "y": 0.0, "w": 0.6, "h": 1.0},
        facecam_ratio=0.5,
    ))
    assert "scale=1080:960" in f  # top zone (cam)
    # ratio is clamped to [0.2, 0.6]
    f2 = _filter_string(_base(
        output_width=1080, output_height=1920,
        facecam_rect={"x": 0.7, "y": 0.7, "w": 0.25, "h": 0.3},
        content_rect={"x": 0.0, "y": 0.0, "w": 0.6, "h": 1.0},
        facecam_ratio=0.9,
    ))
    # 0.6 * 1920 = 1152
    assert "scale=1080:1152" in f2


def test_jump_cuts_two_ranges_interleave_concat_and_split_source():
    f = _filter_string(_base(keep_ranges=[(0.0, 6.0), (8.0, 14.0)]))
    # Source split before trims.
    assert "split=2[jcsrc_v0][jcsrc_v1]" in f
    assert "asplit=2[jcsrc_a0][jcsrc_a1]" in f
    # concat inputs interleaved per segment: v0,a0,v1,a1
    assert "[jv0][ja0][jv1][ja1]concat=n=2:v=1:a=1[jc_v][jc_a]" in f
    # The wrong (old) ordering must NOT appear.
    assert "[jv0][jv1][ja0][ja1]concat" not in f


def test_single_jump_cut_range_is_valid():
    f = _filter_string(_base(keep_ranges=[(1.0, 20.0)]))
    assert "split=1[jcsrc_v0]" in f
    assert "[jv0][ja0]concat=n=1:v=1:a=1[jc_v][jc_a]" in f


def test_cold_open_concat_is_interleaved():
    f = _filter_string(_base(cold_open_hook_start=2.0, cold_open_hook_end=5.0))
    assert "split=3[cosrc_v0][cosrc_v1][cosrc_v2]" in f
    assert "[co_v0][co_a0][co_v1][co_a1][co_v2][co_a2]concat=n=3:v=1:a=1" in f


def test_full_chain_each_intermediate_label_consumed_once():
    """No intermediate pad is read more than once outside of split/asplit."""
    f = _filter_string(_base(
        facecam_rect={"x": 0.7, "y": 0.71, "w": 0.255, "h": 0.29},
        content_rect={"x": 0.04, "y": 0.0, "w": 0.63, "h": 1.0},
        facecam_ratio=0.42,
        keep_ranges=[(0.0, 6.0), (8.0, 14.0)],
        cold_open_hook_start=2.0, cold_open_hook_end=5.0,
    ))
    # composed_v/jc_v/co_v are each defined once and consumed once.
    for label in ("composed_v", "jc_v", "co_v"):
        produced = len(re.findall(rf"\]\[?{label}\]", f)) + f.count(f"[{label}]")
        # crude: label should appear as producer once and consumer once → 2 refs
        assert f.count(f"[{label}]") == 2, f"{label} appears {f.count(f'[{label}]')} times"
