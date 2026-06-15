"""Tests for the Whisper hallucination filter.

Long stream VODs transcribed in CPU/standard mode used to emit boilerplate like
"Sous-titres réalisés par la communauté d'Amara.org" over silent/music stretches
(VAD was disabled for >1h files). The filter drops those non-speech ghosts while
keeping genuine — even profane — stream speech.
"""

from __future__ import annotations

import pytest

from forge_engine.services.transcription import (
    _is_hallucinated_segment,
    _normalize_for_match,
)


@pytest.mark.parametrize(
    "text,confidence,expected",
    [
        # Known boilerplate hallucinations → dropped
        ("Sous-titres réalisés par la communauté d'Amara.org", 0.30, True),
        ("Sous-titrage ST'501", 0.50, True),
        ("Merci d'avoir regardé cette vidéo", 0.40, True),
        ("Abonnez-vous à la chaîne", 0.50, True),
        ("N'oubliez pas de vous abonner", 0.60, True),
        ("Thanks for watching", 0.50, True),
        ("Please subscribe", 0.50, True),
        ("", 0.90, True),  # empty → noise
        ("euh", 0.10, True),  # low-conf trivial ghost
        # Genuine stream speech → kept (even low-ish confidence, even profanity)
        ("Wesh les gars on est là pour le match", 0.90, False),
        ("Putain c'est incroyable ce but", 0.85, False),
        ("Allez", 0.95, False),
        ("Non mais attends, regarde ça", 0.55, False),
        # A real but short word at decent confidence is kept
        ("Ouais", 0.70, False),
    ],
)
def test_is_hallucinated_segment(text, confidence, expected):
    assert _is_hallucinated_segment(text, confidence) is expected


def test_normalize_strips_accents_and_punctuation():
    assert _normalize_for_match("Réalisés, par!") == "realises  par"
    assert "amara.org" in _normalize_for_match("Amara.ORG")


def test_none_confidence_does_not_crash():
    # word_timestamps off → confidence is None; boilerplate still dropped,
    # genuine speech still kept.
    assert _is_hallucinated_segment("amara.org", None) is True
    assert _is_hallucinated_segment("on lance le stream", None) is False
