"""Tests for the no-LLM title heuristic — picking the punchiest clause instead
of a weak mid-sentence opener, while avoiding too-vague fragments."""

from __future__ import annotations

from dataclasses import dataclass

from forge_engine.services.auto_pipeline import _best_hook_clause, _heuristic_caption


def test_prefers_question_with_substance():
    t = "Bon alors voilà quoi. Comment il connait Tom Brady ? Enfin bref."
    assert _best_hook_clause(t) == "Comment il connait Tom Brady ?"


def test_skips_too_vague_fragment():
    # "Dans quel sens ?" is too short → the substantial clause wins.
    t = "Dans quel sens ? Mais ils ont pas eu d'autre occasion cette saison."
    out = _best_hook_clause(t)
    assert out != "Dans quel sens ?"
    assert "occasion" in out


def test_intensifier_clause_beats_flat_opener():
    t = "Ouais donc en fait je disais. Putain c'est incroyable ce qu'il fait là."
    assert "incroyable" in _best_hook_clause(t).lower()


@dataclass
class FakeSeg:
    transcript: str
    score_tags: list | None = None
    topic_label: str | None = None


def test_heuristic_caption_quotes_and_tags():
    seg = FakeSeg(
        transcript="Bla bla bla. Comment il connait Tom Brady ? voilà.",
        score_tags=["clutch", "fail"],
    )
    title, desc, tags = _heuristic_caption(seg, 0, "EtoStark")
    assert title == '"Comment il connait Tom Brady ?"'
    assert "#etostark" in tags
    assert "#clutch" in tags


def test_heuristic_caption_falls_back_without_transcript():
    seg = FakeSeg(transcript="", topic_label="Le moment fort")
    title, _, _ = _heuristic_caption(seg, 2, "EtoStark")
    assert title == "Le moment fort"
