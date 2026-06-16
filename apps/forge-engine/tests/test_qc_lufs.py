"""Test ebur128 LUFS parsing — guards the regression where the QC read the
first-frame integrated loudness (-70) instead of the final Summary value,
falsely flagging every clip as 'audio too quiet'."""

from __future__ import annotations

from forge_engine.services.qc import _parse_ebur128_lufs

# Realistic ffmpeg ebur128 stderr: continuous per-frame lines (first frame
# integrated is ~-70) followed by the Summary block.
SAMPLE = """\
[Parsed_ebur128_0 @ 0x7f] t: 0.0999896  TARGET:-23 LUFS    M:-120.7 S:-120.7     I: -70.0 LUFS       LRA:   0.0 LU
[Parsed_ebur128_0 @ 0x7f] t: 0.2        TARGET:-23 LUFS    M: -22.1 S: -30.4     I: -25.3 LUFS       LRA:   2.1 LU
[Parsed_ebur128_0 @ 0x7f] t: 60.0       TARGET:-23 LUFS    M: -13.9 S: -14.0     I: -14.2 LUFS       LRA:   5.0 LU
[Parsed_ebur128_0 @ 0x7f] Summary:

  Integrated loudness:
    I:         -14.2 LUFS
    Threshold: -24.6 LUFS

  Loudness range:
    LRA:         5.0 LU
"""


def test_takes_final_integrated_loudness_not_first_frame():
    assert _parse_ebur128_lufs(SAMPLE) == -14.2


def test_quiet_clip_reports_quiet():
    quiet = (
        "[Parsed_ebur128_0 @ 0x7f] t: 0.1 I: -70.0 LUFS LRA: 0.0 LU\n"
        "[Parsed_ebur128_0 @ 0x7f] Summary:\n"
        "  Integrated loudness:\n"
        "    I:         -45.0 LUFS\n"
    )
    assert _parse_ebur128_lufs(quiet) == -45.0


def test_no_loudness_lines_returns_none():
    assert _parse_ebur128_lufs("nothing here\njust text\n") is None
    assert _parse_ebur128_lufs("") is None
