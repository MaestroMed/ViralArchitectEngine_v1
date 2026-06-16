"""Tests for LLM title cleaning + quality gating.

A small local model returns viral hooks but with artifacts (wrapping <>, quotes,
"Titre accrocheur :" preambles) and sometimes garbage (raw transcript, run-ons).
We clean the artifacts and gate out the garbage so it falls back to the
deterministic heuristic.
"""

from __future__ import annotations

import pytest

from forge_engine.services.content_generation import ContentGenerationService as C


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("<Rage dans le jeu !", "Rage dans le jeu !"),
        ('"Le flot de partir"', "Le flot de partir"),
        ("1. Débat enflammé", "Débat enflammé"),
        ("Titre accrocheur : Le joueur épuisé", "Le joueur épuisé"),
        ("Voici un titre : Surprise totale", "Surprise totale"),
        ("🤣 Le streameur ! > 😂", "🤣 Le streameur ! 😂"),
        ("«Incroyable»", "Incroyable"),
    ],
)
def test_clean_title(raw, expected):
    assert C._clean_title(raw) == expected


def test_quality_gate_accepts_good_hook():
    assert C.is_quality_title("😱 Désolé, mais c'est pas fatigué ! 👊")


def test_quality_gate_rejects_empty_and_too_long():
    assert not C.is_quality_title("")
    assert not C.is_quality_title("a")
    assert not C.is_quality_title("x" * 90)


def test_quality_gate_rejects_transcript_runon():
    tr = "je sais pas voilà, un arabe, un noir, moi ça me vient, moi je signe"
    assert not C.is_quality_title(tr, tr)               # echoes transcript
    assert not C.is_quality_title("a, b, c, d, e long", "")  # comma run-on
