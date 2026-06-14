"""Quality boosters for the virality scorer.

These are surgical adjustments to ``_score_segment``'s six dimensions,
applied as post-hoc deltas so the rest of the pipeline (LLM merging,
emotion merging, deduplication) keeps working unchanged.

Why this lives in its own module:
- ``ViralityScorer._score_segment`` is already 200+ lines. Inlining the new
  rules there makes it unreadable and harder to A/B.
- Each booster is independently testable with deterministic transcript
  fixtures (no GPU, no LLM).
- Feature-flagged via ``FORGE_VIRALITY_QUALITY_V2`` so we can ship the new
  defaults but flip back instantly if a regression shows up on real VODs.

Boosters applied in V2:
1. **Duration recalibration** — TikTok's 2026 algorithm rewards completion
   rate, which favours 20-45s clips. The legacy 45-90s sweet spot was tuned
   when 60s was the platform cap. Shorter clips get the bigger payoff bonus.
2. **Filler-word penalty** — "euh / bah / donc voilà / tu vois" dilute the
   content; high filler ratio dings ``clarity_autonomy``.
3. **Lead-silence detection** — a clip with 2+s of dead air before speech
   loses the viewer in the first second. We surface a ``recommended_start``
   timestamp in the score result; the export pipeline uses it to trim.
4. **Combo bonus** — co-occurrence of (hook + humour) or (surprise +
   tension) is rare and viral. Boosts payoff by up to +3 when both axes
   pass a threshold.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# ─── Tunables ────────────────────────────────────────────────────────────────

# 2026 TikTok / Shorts / Reels: completion rate is the dominant signal.
# Shorter clips reliably complete; the 45-90s window was optimal in 2022 but
# is now mid. These bands replace the legacy duration bonus in `payoff`.
DURATION_OPTIMAL_RANGE = (20.0, 45.0)   # +5 bonus
DURATION_GOOD_RANGE = (12.0, 60.0)      # +3 bonus
DURATION_PENALTY_THRESHOLD = 75.0       # over this, -2

# Filler / hesitation markers. Conservative list — "ben" and "alors" are too
# common in genuine FR speech to penalise. We focus on words that signal
# stalling or empty filler.
FILLER_PATTERN = re.compile(
    r"\b(euh+|heu+|hmm+|bah\s|j['e]\s*sais\s*pas|tu\s*vois|en\s*fait\s+euh|"
    r"donc\s+voilà|enfin\s+bref|comment\s+dire|c['e]st\s*à\s*dire)\b",
    re.IGNORECASE,
)

# Filler ratio above which we ding clarity. Computed as filler_hits / sentences.
FILLER_RATIO_WARN = 0.20   # -2 clarity
FILLER_RATIO_HEAVY = 0.40  # -4 clarity

# Lead silence: any gap of this many seconds at the start of a segment is
# treated as dead air to trim. We don't trim ourselves — we just surface the
# recommended start timestamp so the cold-open / export step can act on it.
LEAD_SILENCE_THRESHOLD_SEC = 1.2

# Combo bonus: an axis "fires" when its score is at least N% of its weight.
COMBO_FIRE_RATIO = 0.5
COMBO_PAYOFF_BONUS = 3


# ─── Feature flag ────────────────────────────────────────────────────────────

def quality_v2_enabled() -> bool:
    """V2 boosters are ON by default — set FORGE_VIRALITY_QUALITY_V2=0 to
    revert to the legacy scoring. Useful for A/B against historical clips."""
    raw = os.environ.get("FORGE_VIRALITY_QUALITY_V2", "1").lower()
    return raw in ("1", "true", "yes", "on")


# ─── Helpers (also exported for tests) ───────────────────────────────────────

@dataclass(frozen=True)
class DurationBonus:
    delta: int
    reason: str


def duration_bonus(duration: float) -> DurationBonus:
    """Return the payoff delta for the segment's length."""
    low, high = DURATION_OPTIMAL_RANGE
    if low <= duration <= high:
        return DurationBonus(+5, f"Optimal duration ({int(low)}-{int(high)}s)")
    low_g, high_g = DURATION_GOOD_RANGE
    if low_g <= duration <= high_g:
        return DurationBonus(+3, f"Good duration ({int(low_g)}-{int(high_g)}s)")
    if duration > DURATION_PENALTY_THRESHOLD:
        return DurationBonus(-2, f"Too long ({int(duration)}s — completion drops)")
    return DurationBonus(0, "")


def filler_penalty(transcript: str) -> tuple[int, str | None]:
    """Detect filler density and return (delta, reason)."""
    if not transcript.strip():
        return 0, None
    hits = len(FILLER_PATTERN.findall(transcript))
    sentence_count = max(1, len(re.split(r"[.!?]+", transcript)))
    ratio = hits / sentence_count
    if ratio >= FILLER_RATIO_HEAVY:
        return -4, f"Heavy filler density ({hits} hits / {sentence_count} sentences)"
    if ratio >= FILLER_RATIO_WARN:
        return -2, f"Filler density above target ({hits} hits)"
    return 0, None


def detect_lead_silence(
    segment_start: float,
    transcript_segments: Iterable[dict[str, Any]] | None,
) -> tuple[float | None, str | None]:
    """Return (recommended_start, reason) if there's dead air at the head.

    Looks at the first transcript sub-segment's start vs segment_start. If
    the gap exceeds LEAD_SILENCE_THRESHOLD_SEC, we recommend trimming to
    just before the first word. Returns (None, None) when nothing to do.
    """
    if not transcript_segments:
        return None, None
    first = next(iter(transcript_segments), None)
    if first is None:
        return None, None
    first_word_start = first.get("start")
    if first_word_start is None:
        return None, None
    gap = first_word_start - segment_start
    if gap < LEAD_SILENCE_THRESHOLD_SEC:
        return None, None
    # Trim to 0.2s before first word so we never cut mid-syllable.
    recommended = max(segment_start, first_word_start - 0.2)
    return recommended, f"Lead silence trimmed ({gap:.1f}s of dead air)"


def combo_bonus(score: dict[str, int]) -> tuple[int, str | None]:
    """Reward rare combinations of dimensions firing together.

    Defined on the raw dimension scores in ``score`` (hook_strength, payoff,
    humour_reaction, tension_surprise, ...). We require both members of a
    pair to clear COMBO_FIRE_RATIO of their max weight.
    """
    fired_hook = score.get("hook_strength", 0) >= 25 * COMBO_FIRE_RATIO
    fired_humour = score.get("humour_reaction", 0) >= 15 * COMBO_FIRE_RATIO
    fired_surprise = (
        # tension_surprise is the axis name carrying both surprise + tension.
        score.get("tension_surprise", 0) >= 15 * COMBO_FIRE_RATIO
    )
    fired_payoff = score.get("payoff", 0) >= 20 * COMBO_FIRE_RATIO

    if fired_hook and fired_humour:
        return COMBO_PAYOFF_BONUS, "Combo bonus: strong hook + humour"
    if fired_surprise and fired_payoff:
        return COMBO_PAYOFF_BONUS, "Combo bonus: surprise + payoff"
    return 0, None


# ─── Main entry point ────────────────────────────────────────────────────────

def apply_quality_boosters(
    score: dict[str, Any],
    segment: dict[str, Any],
) -> dict[str, Any]:
    """Mutate ``score`` in place with the V2 boosters and return it.

    Idempotent — re-running on a boosted score detects the marker and
    skips. Safe to call from ``_score_segment``'s tail without risking
    double-application via async retry paths.
    """
    if score.get("_quality_v2_applied"):
        return score
    if not quality_v2_enabled():
        return score

    transcript = segment.get("transcript", "")
    duration = float(segment.get("duration", 0) or 0)

    new_reasons = list(score.get("reasons") or [])

    # 1. Duration recalibration: REPLACE the legacy 45-90s bonus that the
    #    base scorer added (it may have given up to +5 already).
    legacy_marker = "duration"
    score["payoff"] = max(
        0,
        score.get("payoff", 0)
        - _max_legacy_duration_bonus_in(new_reasons, marker=legacy_marker),
    )
    new_reasons = [r for r in new_reasons if "duration" not in r.lower()]
    db = duration_bonus(duration)
    if db.delta:
        score["payoff"] = max(0, min(score.get("payoff", 0) + db.delta, 20))
        new_reasons.append(db.reason)

    # 2. Filler penalty on clarity_autonomy.
    fp_delta, fp_reason = filler_penalty(transcript)
    if fp_delta:
        score["clarity_autonomy"] = max(0, score.get("clarity_autonomy", 0) + fp_delta)
        if fp_reason:
            new_reasons.append(fp_reason)

    # 3. Lead silence: surface a recommended_start without touching scores.
    rec_start, rs_reason = detect_lead_silence(
        segment.get("start_time", 0), segment.get("transcript_segments"),
    )
    if rec_start is not None:
        score["recommended_start"] = rec_start
        if rs_reason:
            new_reasons.append(rs_reason)

    # 4. Combo bonus.
    cb_delta, cb_reason = combo_bonus(score)
    if cb_delta:
        score["payoff"] = min(20, score.get("payoff", 0) + cb_delta)
        if cb_reason:
            new_reasons.append(cb_reason)

    # Recompute total from the (possibly changed) dimensions.
    score["total"] = min(
        100,
        score.get("hook_strength", 0)
        + score.get("payoff", 0)
        + score.get("humour_reaction", 0)
        + score.get("tension_surprise", 0)
        + score.get("clarity_autonomy", 0)
        + score.get("rhythm", 0),
    )
    score["reasons"] = new_reasons[:8]
    score["_quality_v2_applied"] = True
    return score


def _max_legacy_duration_bonus_in(reasons: Iterable[str], marker: str) -> int:
    """The legacy scorer added up to +5 (45-90s) or +3 (60-120s) to payoff
    with reasons like "Optimal duration (45-90s)" / "Good duration ...".
    We need to subtract that BEFORE applying our new bonus, otherwise V1+V2
    would double-count and clip at 20.
    """
    for r in reasons:
        if marker in r.lower():
            if "optimal" in r.lower():
                return 5
            if "good" in r.lower():
                return 3
    return 0
