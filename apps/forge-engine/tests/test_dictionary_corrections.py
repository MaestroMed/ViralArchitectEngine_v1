"""Dictionary corrections must be WHOLE-WORD.

A bare substring sub mangled ordinary French: the etostark hotword set turned
"avez" -> "avEZ", "regardé combien" -> "reGuardian Angelrdé combInfini" (EZ /
Guardian Angel / Infinity Edge bleeding into normal words). These pin that
corrections only fire on word boundaries.
"""

from __future__ import annotations

from forge_engine.services.dictionary import DictionaryService


def _svc():
    s = DictionaryService()
    s._dictionaries = {
        "t": {"corrections": {"ez": "EZ", "karmine": "Karmine Corp", "gardé": "GARDE_FIX"}}
    }
    return s


def test_does_not_bleed_into_substrings():
    s = _svc()
    # "avez" contains "ez", "regardé" contains "gardé" — both must stay intact.
    assert s.apply_corrections("tu avez regardé", "t") == "tu avez regardé"


def test_corrects_standalone_words():
    s = _svc()
    assert s.apply_corrections("ez gg", "t") == "EZ gg"
    assert s.apply_corrections("bien gardé là", "t") == "bien GARDE_FIX là"


def test_multiword_correction_whole_word():
    s = _svc()
    assert s.apply_corrections("vive karmine", "t") == "vive Karmine Corp"


def test_case_insensitive_but_still_whole_word():
    s = _svc()
    # standalone EZ (any case) corrected; "AVEZ" left alone
    assert s.apply_corrections("AVEZ Ez", "t") == "AVEZ EZ"
