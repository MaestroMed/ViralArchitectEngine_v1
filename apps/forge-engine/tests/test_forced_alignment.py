"""Forced aligner — graceful-degradation contract (no model/audio needed).

The accuracy of torchaudio MMS_FA forced_align itself is validated out-of-band;
these pin the WRAPPER's safety: it must never raise and must keep the original
whisper timings whenever it can't align.
"""

from __future__ import annotations

from forge_engine.services.forced_alignment import ForcedAligner


def _tr():
    return {
        "segments": [
            {"start": 0.0, "end": 5.0, "words": [
                {"word": "bonjour", "start": 0.0, "end": 1.0},
                {"word": "tout", "start": 1.0, "end": 1.5},
            ]}
        ]
    }


async def test_unavailable_returns_input_unchanged():
    al = ForcedAligner()
    al._available = False  # torchaudio/MMS_FA absent
    tr = _tr()
    out = await al.align_transcription("/does/not/exist.wav", tr)
    assert out is tr
    assert "alignment_method" not in out
    assert out["segments"][0]["words"][0]["start"] == 0.0


async def test_setup_failure_degrades_gracefully(monkeypatch):
    al = ForcedAligner()
    al._available = True  # claim available, but make model load blow up

    def boom():
        raise RuntimeError("model load failed")

    monkeypatch.setattr(al, "_ensure_model", boom)
    tr = _tr()
    out = await al.align_transcription("/does/not/exist.wav", tr)
    # Original timings preserved, no crash, not marked as aligned.
    assert out["segments"][0]["words"][0]["start"] == 0.0
    assert "alignment_method" not in out


async def test_bad_audio_path_degrades_gracefully(monkeypatch):
    al = ForcedAligner()
    al._available = True
    monkeypatch.setattr(al, "_ensure_model", lambda: None)  # skip real model
    al._dictionary = {"a": 1}
    tr = _tr()
    out = await al.align_transcription("/no/such/audio.wav", tr)
    assert out["segments"][0]["words"][0]["start"] == 0.0
    assert "alignment_method" not in out
