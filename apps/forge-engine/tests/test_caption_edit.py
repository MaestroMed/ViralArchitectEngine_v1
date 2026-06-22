"""Caption-edit frame math + word remap — the bit that must be exactly right."""

from __future__ import annotations

from forge_engine.services.caption_edit import apply_caption_edits, caption_lines_for_clip

ABS_SEGS = [
    {"start": 100.5, "end": 102.0, "text": "tu avEZ vu", "words": [
        {"word": "tu", "start": 100.5, "end": 100.8},
        {"word": "avEZ", "start": 100.8, "end": 101.3},
        {"word": "vu", "start": 101.3, "end": 102.0},
    ]},
    {"start": 50.0, "end": 51.0, "text": "hors clip", "words": []},  # outside the window
]


def test_lines_are_clip_relative_and_filtered():
    lines = caption_lines_for_clip(ABS_SEGS, clip_start=100.0, clip_end=110.0)
    assert len(lines) == 1                       # the 50s line is filtered out
    assert abs(lines[0]["start"] - 0.5) < 1e-6   # 100.5 - 100.0
    assert lines[0]["words"][0]["start"] == 0.5
    assert lines[0]["text"] == "tu avEZ vu"


def test_typo_fix_keeps_word_timing_and_round_trips_to_absolute():
    lines = caption_lines_for_clip(ABS_SEGS, clip_start=100.0, clip_end=110.0)
    lines[0]["text"] = "tu avez vu"              # fix the typo (same word count)
    segs = apply_caption_edits(lines, clip_start=100.0)
    assert len(segs) == 1
    s = segs[0]
    assert s["start"] == 100.5                   # back to absolute VOD coords
    assert [w["word"] for w in s["words"]] == ["tu", "avez", "vu"]
    # same count → each original (absolute) timing preserved
    assert s["words"][1]["start"] == 100.8 and s["words"][1]["end"] == 101.3


def test_word_count_change_distributes_evenly():
    lines = caption_lines_for_clip(ABS_SEGS, clip_start=100.0, clip_end=110.0)
    lines[0]["text"] = "un deux trois quatre"    # 4 vs 3 → even distribution
    segs = apply_caption_edits(lines, clip_start=100.0)
    w = segs[0]["words"]
    assert len(w) == 4
    assert abs(w[0]["start"] - 100.5) < 1e-6
    assert abs(w[-1]["end"] - 102.0) < 0.02


def test_empty_line_dropped():
    assert apply_caption_edits([{"start": 0, "end": 1, "text": "  ", "words": []}], clip_start=100.0) == []
