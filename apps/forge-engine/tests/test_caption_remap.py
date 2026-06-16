"""Tests for caption timestamp remap onto the post-jump-cut timeline.

Jump cuts trim+concat the video to keep_ranges (clip-relative seconds), which
compresses the timeline. Captions burn AFTER the cut, so their timestamps must
be remapped or karaoke desyncs. Words in removed gaps are dropped.
"""

from __future__ import annotations

from forge_engine.services.export import _remap_caption_times


def test_no_cuts_is_noop():
    segs = [{"start": 1.0, "end": 2.0, "words": [{"word": "a", "start": 1.0, "end": 2.0}]}]
    assert _remap_caption_times(segs, []) is segs


def test_times_compress_onto_cut_timeline():
    # keep [0,5] and [8,12]; gap 5-8 (3s) removed → post-cut 0-5 then 5-9.
    keep = [(0, 5), (8, 12)]
    segs = [
        {"start": 1.0, "end": 4.0, "words": [{"word": "a", "start": 1.0, "end": 2.0}]},
        {"start": 9.0, "end": 11.0, "words": [{"word": "c", "start": 9.0, "end": 10.0}]},
    ]
    out = _remap_caption_times(segs, keep)
    assert round(out[0]["start"], 1) == 1.0           # first range unchanged
    assert round(out[1]["start"], 1) == 6.0           # 9 → 5 + (9-8) = 6
    assert round(out[1]["words"][0]["start"], 1) == 6.0


def test_segment_fully_in_removed_gap_is_dropped():
    keep = [(0, 5), (8, 12)]
    segs = [{"start": 6.0, "end": 7.0, "words": [{"word": "gap", "start": 6.0, "end": 7.0}]}]
    assert _remap_caption_times(segs, keep) == []


def test_last_end_within_new_duration():
    keep = [(0, 5), (8, 12)]   # new duration = 9s
    segs = [{"start": 11.0, "end": 12.0, "words": [{"word": "z", "start": 11.0, "end": 12.0}]}]
    out = _remap_caption_times(segs, keep)
    assert out and out[-1]["end"] <= 9.0 + 1e-6


def test_words_in_gap_dropped_but_segment_kept():
    keep = [(0, 5), (8, 12)]
    segs = [{
        "start": 4.0, "end": 9.0,
        "words": [
            {"word": "keep1", "start": 4.0, "end": 4.5},   # in range 1
            {"word": "gap", "start": 6.0, "end": 6.5},      # removed → dropped
            {"word": "keep2", "start": 8.5, "end": 9.0},    # in range 2
        ],
    }]
    out = _remap_caption_times(segs, keep)
    assert len(out) == 1
    words = [w["word"] for w in out[0]["words"]]
    assert "gap" not in words and "keep1" in words and "keep2" in words
