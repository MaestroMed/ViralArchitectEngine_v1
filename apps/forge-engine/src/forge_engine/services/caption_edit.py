"""Helpers for the editor's caption-text edit.

The editor shows clip-RELATIVE caption lines, the user fixes the text, and sends
them back. We convert to ABSOLUTE VOD seconds (the frame run_export's caption
builder expects, since it re-subtracts clip_start) and re-derive word-level
timings: when the edited line keeps the same word count we preserve each word's
original timing (perfect for a typo fix); otherwise we spread the line's span
evenly across the new words.
"""

from __future__ import annotations

from typing import Any


def caption_lines_for_clip(
    all_segments: list[dict[str, Any]], clip_start: float, clip_end: float
) -> list[dict[str, Any]]:
    """Clip-RELATIVE caption lines for [clip_start, clip_end] (absolute), for the
    editor to display + edit: ``{start, end, text, words:[{word,start,end}]}``."""
    lines: list[dict[str, Any]] = []
    for seg in all_segments:
        s = float(seg.get("start", 0.0))
        if not (clip_start <= s <= clip_end):
            continue
        words = [
            {
                "word": w.get("word", ""),
                "start": round(float(w.get("start", 0.0)) - clip_start, 3),
                "end": round(float(w.get("end", 0.0)) - clip_start, 3),
            }
            for w in (seg.get("words") or [])
        ]
        lines.append({
            "start": round(s - clip_start, 3),
            "end": round(float(seg.get("end", s)) - clip_start, 3),
            "text": (seg.get("text") or " ".join(w["word"] for w in words)).strip(),
            "words": words,
        })
    return lines


def _rebuild_words(text: str, start: float, end: float, original: list[dict] | None) -> list[dict[str, Any]]:
    toks = text.split()
    if not toks:
        return []
    # Same word count → keep each original word's timing (typo-fix case).
    if original and len(original) == len(toks):
        return [
            {"word": t, "start": ow.get("start", start), "end": ow.get("end", end)}
            for t, ow in zip(toks, original)
        ]
    span = max(0.01, end - start) / len(toks)
    return [
        {"word": t, "start": round(start + i * span, 3), "end": round(start + (i + 1) * span, 3)}
        for i, t in enumerate(toks)
    ]


def apply_caption_edits(edited_lines: list[dict[str, Any]], clip_start: float) -> list[dict[str, Any]]:
    """Editor's clip-relative edited lines → ABSOLUTE transcript segments with
    re-derived word timings, ready to pass as run_export(transcript_override=...)."""
    segs: list[dict[str, Any]] = []
    for line in edited_lines:
        start = float(line.get("start", 0.0)) + clip_start
        end = float(line.get("end", line.get("start", 0.0))) + clip_start
        text = (line.get("text") or "").strip()
        if not text:
            continue
        original_abs = None
        if line.get("words"):
            original_abs = [
                {**w, "start": float(w.get("start", 0.0)) + clip_start, "end": float(w.get("end", 0.0)) + clip_start}
                for w in line["words"]
            ]
        segs.append({
            "start": start,
            "end": end,
            "text": text,
            "words": _rebuild_words(text, start, end, original_abs),
        })
    return segs
