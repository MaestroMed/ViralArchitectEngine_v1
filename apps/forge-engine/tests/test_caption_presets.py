"""Dynamic caption presets — colour + animated word-pop + edited-text passthrough."""

from __future__ import annotations

from forge_engine.services.captions import CAPTION_PRESETS, CaptionEngine

SEG = [{
    "start": 0.0, "end": 2.0,
    "words": [
        {"word": "salut", "start": 0.0, "end": 0.5},
        {"word": "les", "start": 0.5, "end": 0.8},
        {"word": "amis", "start": 0.8, "end": 1.4},
    ],
}]


def test_all_presets_registered():
    assert {"classic", "hormozi", "pop", "minimal", "neon"} <= set(CAPTION_PRESETS)


def test_preset_colours_differ():
    eng = CaptionEngine()
    classic = eng.generate_ass(SEG, style_name="classic")
    hormozi = eng.generate_ass(SEG, style_name="hormozi")
    assert "&H0000FFFF" in classic   # yellow active word
    assert "&H0066FF00" in hormozi   # green active word


def test_pop_preset_eases_active_word():
    eng = CaptionEngine()
    classic = eng.generate_ass(SEG, style_name="classic")
    hormozi = eng.generate_ass(SEG, style_name="hormozi")
    assert "\\t(0,120" not in classic   # classic = static bump
    assert "\\t(0,120" in hormozi       # hormozi = eased pop-in


def test_all_caps_applied():
    eng = CaptionEngine()
    assert "SALUT" in eng.generate_ass(SEG, style_name="classic")


def test_unknown_preset_falls_back_to_classic():
    eng = CaptionEngine()
    out = eng.generate_ass(SEG, style_name="does-not-exist")
    assert "Dialogue:" in out
    assert "&H0000FFFF" in out  # classic yellow


def test_custom_overrides_convert_hex_and_layer_on_preset():
    # The editor's fine-tune colours (#RRGGBB) override the preset, converted to
    # ASS &HAABBGGRR — this was the dead link that made custom colours a no-op.
    eng = CaptionEngine()
    out = eng.generate_ass(SEG, style_name="hormozi", custom_style={
        "color": "#FF0000", "highlightColor": "#00FF00", "fontFamily": "Inter",
    })
    assert "&H000000FF" in out   # #FF0000 red -> primary
    assert "&H0000FF00" in out   # #00FF00 green -> active highlight (overrode preset green-ish)
    assert "Inter" in out        # font family override applied


def test_position_top_sets_top_alignment():
    eng = CaptionEngine()
    out = eng.generate_ass(SEG, style_name="classic", custom_style={"position": "top"})
    # Style line alignment field = 8 (top-center)
    style_line = next(line for line in out.splitlines() if line.startswith("Style: Default"))
    assert style_line.split(",")[18] == "8"


def test_edited_captions_pass_through():
    # The editor fixes a typo by passing corrected segments — they render verbatim.
    eng = CaptionEngine()
    edited = [{"start": 0.0, "end": 1.0, "words": [{"word": "corrigé", "start": 0.0, "end": 1.0}]}]
    assert "CORRIGÉ" in eng.generate_ass(edited, style_name="classic")
