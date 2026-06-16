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
    # Fraction of output height given to the facecam zone (top) in the
    # two-zone vstack layout. Clamped to [0.2, 0.6] in build_command().
    facecam_ratio: float = 0.4

    # Source dimensions (needed for animated face tracking crop)
    source_width: int = 1920
    source_height: int = 1080

    # Face tracking — animated SmartCrop keyframes
    # Each entry: {time: float, crop: {x,y,width,height} (0-1 normalized), zoom: float}
    facecam_keyframes: list = field(default_factory=list)

    # Subtitles
    ass_path: Path | None = None       # Pre-generated ASS file
    fonts_dir: Path | None = None      # Dir of bundled fonts for libass (Anton…)

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
            # Two-zone vertical "reaction" layout: facecam crop stacked on top,
            # content crop below. Crops are fractions of the SOURCE frame (not
            # the output), and the source pad is split so each crop reads its own
            # copy — reading [0:v] twice crashed FFmpeg ("Error reinitializing
            # filters"). Heights are even and sum exactly to out_h for vstack.
            sw = cfg.source_width or 1920
            sh = cfg.source_height or 1080

            def _crop_px(rect: dict) -> tuple[int, int, int, int]:
                x = max(0, int(rect["x"] * sw)) & ~1
                y = max(0, int(rect["y"] * sh)) & ~1
                w = max(2, min(int(rect["w"] * sw), sw - x)) & ~1
                h = max(2, min(int(rect["h"] * sh), sh - y)) & ~1
                return x, y, w, h

            f_x, f_y, f_w, f_h = _crop_px(cfg.facecam_rect)
            c_x, c_y, c_w, c_h = _crop_px(cfg.content_rect)

            ratio = max(0.2, min(cfg.facecam_ratio or 0.4, 0.6))
            top_h = int(out_h * ratio) & ~1
            bot_h = out_h - top_h  # out_h and top_h even → bot_h even

            filters.append(
                f"[{source_idx}:v]split=2[lz_f][lz_c];"
                f"[lz_f]crop={f_w}:{f_h}:{f_x}:{f_y},"
                f"scale={out_w}:{top_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{top_h}[cam_z];"
                f"[lz_c]crop={c_w}:{c_h}:{c_x}:{c_y},"
                f"scale={out_w}:{bot_h}:force_original_aspect_ratio=increase,"
                f"crop={out_w}:{bot_h}[content_z];"
                f"[cam_z][content_z]vstack[composed_v]"
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
            n = len(cfg.keep_ranges)
            # Split the source into N copies first: each trim must read its own
            # pad (consuming [composed_v] N times crashes with "Error
            # reinitializing filters").
            vsplit = "".join(f"[jcsrc_v{i}]" for i in range(n))
            asplit = "".join(f"[jcsrc_a{i}]" for i in range(n))
            filters.append(
                f"[{current_v}]split={n}{vsplit};[{current_a}]asplit={n}{asplit}"
            )
            for i, (start, end) in enumerate(cfg.keep_ranges):
                filters.append(
                    f"[jcsrc_v{i}]trim={start:.4f}:{end:.4f},setpts=PTS-STARTPTS[jv{i}];"
                    f"[jcsrc_a{i}]atrim={start:.4f}:{end:.4f},asetpts=PTS-STARTPTS[ja{i}]"
                )
            # concat with v=1:a=1 expects pads interleaved PER SEGMENT
            # (v0,a0,v1,a1,…), NOT all videos then all audios — otherwise the
            # filtergraph fails with a media-type mismatch.
            concat_in = "".join(f"[jv{i}][ja{i}]" for i in range(n))
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
            def _esc(p: str) -> str:
                return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

            ass_escaped = _esc(str(cfg.ass_path))
            sub = f"subtitles={ass_escaped}"
            # Point libass at the bundled fonts so the Anton caption font always
            # renders — otherwise libass falls back to a generic system font and
            # the captions look amateur.
            if cfg.fonts_dir and Path(cfg.fonts_dir).is_dir():
                sub += f":fontsdir={_esc(str(cfg.fonts_dir))}"
            filters.append(
                f"[{current_v}]{sub}[sub_v]"
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
