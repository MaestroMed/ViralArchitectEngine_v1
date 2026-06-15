"""
Single-pass FFmpeg pipeline builder.
Assembles all export transformations into one filter_complex call
instead of sequential re-encodes.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the single-pass export pipeline."""
    # Source
    source_path: Path
    segment_start: float
    segment_duration: float

    # Layout
    output_width: int = 1080
    output_height: int = 1920
    facecam_rect: dict | None = None   # {x, y, w, h} normalized 0-1
    content_rect: dict | None = None

    # Source dimensions (needed for animated face tracking crop)
    source_width: int = 1920
    source_height: int = 1080

    # Face tracking — animated SmartCrop keyframes
    # Each entry: {time: float, crop: {x,y,width,height} (0-1 normalized), zoom: float}
    facecam_keyframes: list = field(default_factory=list)

    # Subtitles
    ass_path: Path | None = None       # Pre-generated ASS file

    # Jump cuts — list of (start, end) in clip-relative seconds to KEEP
    keep_ranges: list = field(default_factory=list)  # [(start, end), ...]

    # Cold open — if set, reorder: hook first, then rest
    cold_open_hook_start: float | None = None
    cold_open_hook_end: float | None = None

    # Intro overlay
    intro_path: Path | None = None     # Pre-rendered intro clip
    intro_duration: float = 0.0

    # Music
    music_path: Path | None = None
    music_volume: float = 0.15
    speech_volume: float = 1.0

    # Output
    output_path: Path = field(default_factory=lambda: Path("output.mp4"))
    fps: int = 30
    crf: int = 18
    use_nvenc: bool = False
    audio_bitrate: str = "192k"
    platform: str = "tiktok"  # tiktok | youtube_shorts | instagram | twitter


class PipelineSinglePass:
    """
    Builds a single FFmpeg invocation that applies:
      1. Segment extraction from source
      2. Layout composition (facecam + content background)
      3. Jump cuts (silence removal) via trim+concat
      4. Cold open reorder (hook first)
      5. Intro overlay blend
      6. Subtitle burn (ASS)
      7. Music mix

    Returns the FFmpeg command as a list of arguments.
    """

    def __init__(self, config: PipelineConfig):
        self.cfg = config

    def build_command(self) -> list[str]:
        """Build the full ffmpeg command."""
        cfg = self.cfg
        inputs: list[str] = []
        filters: list[str] = []
        current_v = "composed_v"
        current_a = "composed_a"

        # ── Input 0: source video ──────────────────────────────────────────
        inputs += ["-ss", str(cfg.segment_start), "-t", str(cfg.segment_duration),
                   "-i", str(cfg.source_path)]
        source_idx = 0

        # ── Step 1: Scale/Compose layout ──────────────────────────────────
        out_w, out_h = cfg.output_width, cfg.output_height

        if cfg.facecam_rect and cfg.content_rect:
            # Two-zone layout: content background + facecam overlay
            fr = cfg.facecam_rect  # normalized {x, y, w, h}
            cr = cfg.content_rect

            # Pixel coords (force even dimensions for libx264)
            c_x = int(cr["x"] * out_w)
            c_y = int(cr["y"] * out_h)
            c_w = int(cr["w"] * out_w) & ~1
            c_h = int(cr["h"] * out_h) & ~1
            f_x = int(fr["x"] * out_w)
            f_y = int(fr["y"] * out_h)
            f_w = int(fr["w"] * out_w) & ~1
            f_h = int(fr["h"] * out_h) & ~1

            # Facecam stream: animated tracking crop or static crop
            if cfg.facecam_keyframes:
                from forge_engine.services.facecam_tracking import FacecamTracker
                _tracker = FacecamTracker()
                facecam_filter = _tracker.generate_ffmpeg_filter(
                    cfg.facecam_keyframes,
                    input_width=cfg.source_width,
                    input_height=cfg.source_height,
                    output_width=f_w,
                    output_height=f_h,
                    fps=cfg.fps,
                    segment_start=cfg.segment_start,
                )
                logger.debug("[Pipeline] Using animated face-tracking crop for facecam")
            else:
                facecam_filter = (
                    f"crop={f_w}:{f_h}:{f_x}:{f_y},scale={f_w}:{f_h}"
                )

            filters.append(
                # Black canvas
                f"color=black:{out_w}x{out_h}:r={cfg.fps}[canvas];"
                # Content zone — scale source crop to zone size
                f"[{source_idx}:v]crop={c_w}:{c_h}:{c_x}:{c_y},"
                f"scale={c_w}:{c_h}[content_scaled];"
                # Facecam zone — animated tracking or static crop
                f"[{source_idx}:v]{facecam_filter}[facecam_scaled];"
                # Compose on canvas
                f"[canvas][content_scaled]overlay={c_x}:{c_y}[with_content];"
                f"[with_content][facecam_scaled]overlay={f_x}:{f_y}[composed_v]"
            )
        else:
            # Single zone: scale full source to output size
            filters.append(
                f"[{source_idx}:v]scale={out_w}:{out_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{out_h}[composed_v]"
            )

        filters.append(f"[{source_idx}:a]anull[composed_a]")

        # ── Step 2: Jump cuts ─────────────────────────────────────────────
        if cfg.keep_ranges:
            segs_v = []
            segs_a = []
            for i, (start, end) in enumerate(cfg.keep_ranges):
                filters.append(
                    f"[{current_v}]trim={start:.4f}:{end:.4f},setpts=PTS-STARTPTS[jv{i}];"
                    f"[{current_a}]atrim={start:.4f}:{end:.4f},asetpts=PTS-STARTPTS[ja{i}]"
                )
                segs_v.append(f"[jv{i}]")
                segs_a.append(f"[ja{i}]")
            n = len(cfg.keep_ranges)
            concat_in = "".join(segs_v + segs_a)
            filters.append(
                f"{concat_in}concat=n={n}:v=1:a=1[jc_v][jc_a]"
            )
            current_v = "jc_v"
            current_a = "jc_a"

        # ── Step 3: Cold open reorder ─────────────────────────────────────
        if cfg.cold_open_hook_start is not None and cfg.cold_open_hook_end is not None:
            hs = cfg.cold_open_hook_start
            he = cfg.cold_open_hook_end
            # Segments: [hook][pre-hook][post-hook]
            # A filter-pad output can only be consumed once — reading
            # [current_v] three times made FFmpeg fail with "Error
            # reinitializing filters" on the concat. split/asplit first so each
            # trim reads its own copy of the source.
            filters.append(
                f"[{current_v}]split=3[cosrc_v0][cosrc_v1][cosrc_v2];"
                f"[{current_a}]asplit=3[cosrc_a0][cosrc_a1][cosrc_a2];"
                f"[cosrc_v0]trim={hs:.4f}:{he:.4f},setpts=PTS-STARTPTS[co_v0];"
                f"[cosrc_a0]atrim={hs:.4f}:{he:.4f},asetpts=PTS-STARTPTS[co_a0];"
                f"[cosrc_v1]trim=0:{hs:.4f},setpts=PTS-STARTPTS[co_v1];"
                f"[cosrc_a1]atrim=0:{hs:.4f},asetpts=PTS-STARTPTS[co_a1];"
                f"[cosrc_v2]trim={he:.4f},setpts=PTS-STARTPTS[co_v2];"
                f"[cosrc_a2]atrim={he:.4f},asetpts=PTS-STARTPTS[co_a2];"
                f"[co_v0][co_a0][co_v1][co_a1][co_v2][co_a2]concat=n=3:v=1:a=1[co_v][co_a]"
            )
            current_v = "co_v"
            current_a = "co_a"

        # ── Step 4: Subtitle burn ─────────────────────────────────────────
        if cfg.ass_path and cfg.ass_path.exists():
            # Escape for FFmpeg's filtergraph parser. The whole -filter_complex is
            # passed as ONE subprocess arg (no shell), so the value must NOT be
            # wrapped in literal single quotes — FFmpeg 8.x rejects
            # subtitles='...' with "No option name near ...". Escape ':' and "'"
            # instead.
            ass_escaped = (
                str(cfg.ass_path)
                .replace("\\", "/")
                .replace(":", "\\:")
                .replace("'", "\\'")
            )
            filters.append(
                f"[{current_v}]subtitles={ass_escaped}[sub_v]"
            )
            current_v = "sub_v"

        # ── Step 5: Intro overlay ─────────────────────────────────────────
        if cfg.intro_path and cfg.intro_path.exists() and cfg.intro_duration > 0:
            inputs += ["-i", str(cfg.intro_path)]
            intro_input_idx = inputs.count("-i") - 1
            filters.append(
                f"[{intro_input_idx}:v][{current_v}]"
                f"overlay=0:0:enable='lte(t,{cfg.intro_duration:.2f})'[intro_v]"
            )
            current_v = "intro_v"

        # ── Step 6: Music mix ─────────────────────────────────────────────
        if cfg.music_path and cfg.music_path.exists():
            inputs += ["-i", str(cfg.music_path)]
            music_input_idx = inputs.count("-i") - 1
            filters.append(
                f"[{current_a}]volume={cfg.speech_volume}[speech_vol];"
                f"[{music_input_idx}:a]volume={cfg.music_volume}[music_vol];"
                f"[speech_vol][music_vol]amix=inputs=2:duration=first:dropout_transition=2[mixed_a]"
            )
            current_a = "mixed_a"

        # ── Final outputs ─────────────────────────────────────────────────
        filters.append(
            f"[{current_v}]format=yuv420p[final_v];"
            f"[{current_a}]anull[final_a]"
        )

        # Platform-specific loudnorm
        platform_loudnorm = self._get_loudnorm_filter(cfg.platform)
        if platform_loudnorm:
            filters.append(f"[final_a]{platform_loudnorm}[norm_a]")
            out_audio_label = "norm_a"
        else:
            out_audio_label = "final_a"

        # Codec selection
        if cfg.use_nvenc:
            vcodec = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(cfg.crf)]
        elif cfg.platform == "youtube_shorts":
            # H.265 for best quality/size ratio on YouTube Shorts (CPU encode)
            vcodec = ["-c:v", "libx265", "-preset", "medium", "-crf", str(cfg.crf), "-tag:v", "hvc1"]
        else:
            vcodec = ["-c:v", "libx264", "-preset", "medium", "-crf", str(cfg.crf)]

        cmd = (
            # Use the configured binary (FORGE_FFMPEG_PATH) — lets an
            # --enable-libass build be pointed at without touching PATH, so
            # subtitle burn-in works. Defaults to "ffmpeg".
            [settings.FFMPEG_PATH, "-y"]
            + inputs
            + ["-filter_complex", ";".join(filters)]
            + ["-map", "[final_v]", "-map", f"[{out_audio_label}]"]
            + vcodec
            + ["-c:a", "aac", "-b:a", cfg.audio_bitrate]
            + ["-r", str(cfg.fps)]
            + ["-movflags", "+faststart"]
            + [str(cfg.output_path)]
        )
        return cmd

    def _get_loudnorm_filter(self, platform: str) -> str | None:
        """Return loudnorm filter string for the target platform LUFS."""
        targets = {
            "tiktok": -14,
            "youtube_shorts": -14,
            "instagram": -16,
            "twitter": -16,
        }
        lufs = targets.get(platform, -14)
        return f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
