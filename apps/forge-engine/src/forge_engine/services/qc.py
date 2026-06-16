"""
Automated Quality Control for exported clips.
Runs ffprobe-based checks on every export and returns a QCReport.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


def _parse_ebur128_lufs(output: str) -> float | None:
    """Parse the integrated loudness (LUFS) from ffmpeg ebur128 stderr.

    ebur128 prints a continuous "t: 0.1 ... I: -70.0 LUFS" line every frame
    (integrated-so-far starts near -70 before audio accumulates), then a final
    Summary "I: -14.2 LUFS". We must take the LAST "I:" value — taking the first
    matched a near-silent first frame and falsely flagged every clip "too quiet".
    """
    last_lufs: float | None = None
    for line in output.split("\n"):
        if "I:" in line and "LUFS" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "I:" and i + 1 < len(parts):
                    try:
                        last_lufs = float(parts[i + 1])
                    except ValueError:
                        pass
    return last_lufs


class QCLevel(StrEnum):
    PASS = "pass"       # All checks passed
    WARNING = "warning" # Minor issues, clip usable
    FAIL = "fail"       # Critical issues, re-export needed


@dataclass
class QCCheck:
    name: str
    passed: bool
    level: QCLevel  # What level failure means (warning or fail)
    message: str
    value: str | None = None
    expected: str | None = None


@dataclass
class QCReport:
    file_path: str
    overall: QCLevel
    checks: list = field(default_factory=list)  # list[QCCheck]
    duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "overall": self.overall.value,
            "passed": self.overall == QCLevel.PASS,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "level": c.level.value,
                    "message": c.message,
                    "value": c.value,
                    "expected": c.expected,
                }
                for c in self.checks
            ],
            "duration_s": self.duration_s,
        }


class QCService:
    """
    Quality control service for exported video clips.
    Runs ffprobe to verify resolution, audio, duration, codec, etc.
    """

    EXPECTED_WIDTH = 1080
    EXPECTED_HEIGHT = 1920
    MAX_LUFS = -8.0        # If louder than this → clipping risk
    MIN_LUFS = -30.0       # If quieter than this → inaudible
    MIN_DURATION = 5.0     # Minimum valid clip duration (seconds)
    MAX_KEYFRAME_INTERVAL = 3.0  # Max seconds between keyframes

    async def run(
        self,
        file_path: Path,
        expected_duration: float | None = None,
        has_audio: bool = True,
        has_subtitles: bool = False,
        ffprobe_path: str = "ffprobe",
    ) -> QCReport:
        """Run all QC checks on the given file."""
        import time
        start = time.time()

        if not file_path.exists():
            return QCReport(
                file_path=str(file_path),
                overall=QCLevel.FAIL,
                checks=[QCCheck("file_exists", False, QCLevel.FAIL, "File does not exist")],
            )

        checks: list[QCCheck] = []

        # 1. Probe video streams
        probe = await self._probe(file_path, ffprobe_path)
        if probe is None:
            return QCReport(
                file_path=str(file_path),
                overall=QCLevel.FAIL,
                checks=[QCCheck("ffprobe", False, QCLevel.FAIL, "ffprobe failed — file may be corrupt")],
            )

        video_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "video"), None
        )
        audio_stream = next(
            (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), None
        )

        # 2. Resolution check
        if video_stream:
            w = int(video_stream.get("width", 0))
            h = int(video_stream.get("height", 0))
            passed = (w == self.EXPECTED_WIDTH and h == self.EXPECTED_HEIGHT)
            checks.append(QCCheck(
                "resolution", passed, QCLevel.FAIL,
                f"Resolution correct {w}x{h}" if passed else f"Incorrect resolution: {w}x{h}",
                value=f"{w}x{h}", expected=f"{self.EXPECTED_WIDTH}x{self.EXPECTED_HEIGHT}",
            ))
        else:
            checks.append(QCCheck("resolution", False, QCLevel.FAIL, "No video stream found"))

        # 3. Duration check
        fmt_duration = float(probe.get("format", {}).get("duration", 0))
        if expected_duration:
            tolerance = 0.5  # 500 ms tolerance
            passed = abs(fmt_duration - expected_duration) <= tolerance
            checks.append(QCCheck(
                "duration", passed, QCLevel.WARNING,
                f"Duration correct ({fmt_duration:.2f}s)" if passed
                else f"Unexpected duration: {fmt_duration:.2f}s (expected {expected_duration:.2f}s ±{tolerance}s)",
                value=f"{fmt_duration:.2f}s", expected=f"{expected_duration:.2f}s",
            ))
        checks.append(QCCheck(
            "min_duration", fmt_duration >= self.MIN_DURATION, QCLevel.FAIL,
            f"Duration sufficient ({fmt_duration:.2f}s)" if fmt_duration >= self.MIN_DURATION
            else f"Clip too short: {fmt_duration:.2f}s",
        ))

        # 4. Audio check
        if has_audio:
            if audio_stream:
                checks.append(QCCheck("audio_stream", True, QCLevel.FAIL, "Audio stream present"))
                # Check audio loudness
                lufs = await self._measure_lufs(file_path, ffprobe_path)
                if lufs is not None:
                    too_loud = lufs > self.MAX_LUFS
                    too_quiet = lufs < self.MIN_LUFS
                    passed = not too_loud and not too_quiet
                    msg = (
                        f"Audio OK ({lufs:.1f} LUFS)" if passed
                        else f"Audio too {'loud' if too_loud else 'quiet'}: {lufs:.1f} LUFS"
                    )
                    checks.append(QCCheck(
                        "audio_loudness", passed, QCLevel.WARNING, msg,
                        value=f"{lufs:.1f} LUFS",
                    ))
            else:
                checks.append(QCCheck("audio_stream", False, QCLevel.FAIL, "No audio stream found"))

        # 5. Pixel format
        if video_stream:
            pix_fmt = video_stream.get("pix_fmt", "")
            passed = pix_fmt == "yuv420p"
            checks.append(QCCheck(
                "pixel_format", passed, QCLevel.WARNING,
                f"Pixel format correct ({pix_fmt})" if passed
                else f"Non-standard pixel format: {pix_fmt} (expected yuv420p)",
                value=pix_fmt, expected="yuv420p",
            ))

        # 6. Codec check
        if video_stream:
            codec = video_stream.get("codec_name", "")
            passed = codec in ("h264", "hevc", "av1")
            checks.append(QCCheck(
                "video_codec", passed, QCLevel.WARNING,
                f"Compatible codec ({codec})" if passed else f"Unusual codec: {codec}",
                value=codec,
            ))

        # 7. File size sanity
        size_mb = file_path.stat().st_size / 1_048_576
        passed = 0.5 <= size_mb <= 500
        checks.append(QCCheck(
            "file_size", passed, QCLevel.WARNING,
            f"File size OK ({size_mb:.1f} MB)" if passed else f"Abnormal file size: {size_mb:.1f} MB",
            value=f"{size_mb:.1f} MB",
        ))

        # Overall result
        has_fail = any(not c.passed and c.level == QCLevel.FAIL for c in checks)
        has_warning = any(not c.passed and c.level == QCLevel.WARNING for c in checks)
        overall = QCLevel.FAIL if has_fail else (QCLevel.WARNING if has_warning else QCLevel.PASS)

        return QCReport(
            file_path=str(file_path),
            overall=overall,
            checks=checks,
            duration_s=round(time.time() - start, 2),
        )

    async def _probe(self, file_path: Path, ffprobe_path: str) -> dict | None:
        """Run ffprobe and return JSON output."""
        try:
            proc = await asyncio.create_subprocess_exec(
                ffprobe_path, "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            return json.loads(stdout)
        except Exception as e:
            logger.error("ffprobe error: %s", e)
            return None

    async def _measure_lufs(self, file_path: Path, ffprobe_path: str) -> float | None:
        """Measure integrated loudness (LUFS) using ffmpeg ebur128 filter."""
        try:
            ffmpeg_path = ffprobe_path.replace("ffprobe", "ffmpeg")
            proc = await asyncio.create_subprocess_exec(
                ffmpeg_path, "-i", str(file_path),
                "-af", "ebur128=peak=true",
                "-f", "null", "-",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            return _parse_ebur128_lufs(stderr.decode())
        except Exception as e:
            logger.debug("LUFS measurement error: %s", e)
        return None
