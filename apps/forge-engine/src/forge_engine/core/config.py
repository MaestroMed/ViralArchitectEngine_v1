"""Application configuration."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App info
    VERSION: str = "1.0.0"
    APP_NAME: str = "FORGE Engine"
    DEBUG: bool = False  # Set FORGE_DEBUG=true in .env for dev mode

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8420
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    # When BIND_LAN is on, main.py overrides HOST to 0.0.0.0 and the auth
    # layer is forced on (see core/auth.py). The regex below is added to the
    # CORS allowlist so that requests from phones/tablets on a private LAN are
    # accepted. Tweak via FORGE_LAN_CORS_REGEX if your network uses a different
    # subnet (e.g. 172.16.0.0/12).
    BIND_LAN: bool = False
    LAN_CORS_REGEX: str = (
        r"https?://("
        r"localhost|127\.0\.0\.1|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?"
    )

    # Paths
    LIBRARY_PATH: Path = Path.home() / "FORGE_LIBRARY"
    DATABASE_PATH: Path = Path.home() / "FORGE_LIBRARY" / "forge.db"
    TEMP_PATH: Path = Path.home() / "FORGE_LIBRARY" / ".temp"

    # FFmpeg
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"
    FORCE_CPU: bool = False
    # Apple Silicon hardware encoder (VideoToolbox). Separate opt-in from the
    # NVIDIA/NVENC path: used when NVENC is absent so renders on M-series Macs
    # are GPU-accelerated instead of falling back to libx264. Deliberately NOT
    # disabled by FORCE_CPU — on a Mac, FORCE_CPU means "no NVIDIA CUDA stack"
    # (it also pins Whisper to CPU, see bottom of this file), which is the
    # normal state where we still want VideoToolbox. Set
    # FORGE_USE_VIDEOTOOLBOX=false for a true pure-libx264 encode
    # (byte-stable / max-fidelity / determinism).
    USE_VIDEOTOOLBOX: bool = True

    # Bundled caption fonts (Anton etc.) — passed to libass `fontsdir` so the
    # subtitle font always renders without a system install. apps/forge-engine/resources/fonts.
    FONTS_DIR: Path = Path(__file__).parent.parent.parent.parent / "resources" / "fonts"

    # Performance optimizations
    SKIP_PROXY_IF_NVENC: bool = True  # Skip proxy creation if NVENC available (faster final render)
    USE_HWACCEL: bool = True  # Use GPU hardware acceleration for decode/encode
    FFMPEG_NVENC_PRESET: str = "p4"  # NVENC preset (p1=fastest, p7=best quality)
    FFMPEG_PROXY_PRESET: str = "p1"  # Ultra-fast for proxy

    # Whisper TURBO - Auto-optimized based on GPU VRAM
    WHISPER_MODEL: str = "large-v3"  # Use FORGE_WHISPER_MODEL=small in .env for fast testing
    WHISPER_DEVICE: str = "cuda"  # GPU enabled
    WHISPER_COMPUTE_TYPE: str = "int8_float16"  # INT8 quantization (faster + less VRAM)
    # Compute type used when running on CPU (no CUDA). int8 is ~2x faster than
    # float32 with negligible quality loss; set to "float32" for max fidelity.
    WHISPER_CPU_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = "fr"  # Default language (FR for streaming content)

    # Twitch chat as a virality signal (chat-velocity / emote bursts fused into
    # scoring). Best-effort: a chat outage never fails a VOD. FORGE_CHAT_SIGNAL=0
    # to disable. Only fires for Twitch-sourced projects.
    CHAT_SIGNAL: bool = True
    WHISPER_NUM_WORKERS: int = 2  # Default, auto-detected based on VRAM
    WHISPER_BATCH_SIZE: int = 16  # Default, auto-detected based on VRAM
    WHISPER_TURBO_MODE: bool = True  # Enable batched inference for maximum speed
    WHISPER_AUTO_OPTIMIZE: bool = True  # Auto-detect optimal batch_size/workers from VRAM

    # Processing
    PROXY_WIDTH: int = 1280
    PROXY_HEIGHT: int = 720
    PROXY_CRF: int = 28
    AUDIO_SAMPLE_RATE: int = 16000

    # Job queue
    MAX_CONCURRENT_JOBS: int = 2
    JOB_TIMEOUT: int = 3600  # 1 hour

    # Parallel downloads (quick win for 1Gbps connection)
    MAX_PARALLEL_DOWNLOADS: int = 4  # 4-6 simultaneous downloads
    DOWNLOAD_CHUNK_CONNECTIONS: int = 8  # yt-dlp aria2c connections per download

    # Output
    OUTPUT_WIDTH: int = 1080
    OUTPUT_HEIGHT: int = 1920
    OUTPUT_FPS: int = 30
    OUTPUT_CRF: int = 23

    # Export pipeline
    EXPORT_SINGLE_PASS: bool = True  # Use single-pass FFmpeg pipeline (faster)

    # Platform-specific export presets
    PLATFORM_PRESETS: dict = {
        "tiktok": {
            "width": 1080, "height": 1920, "fps": 30,
            "max_duration": 180, "crf": 23,  # TikTok allows long clips; cap at 3min
            "codec": "libx264", "audio_bitrate": "192k",
            "target_lufs": -14, "max_file_mb": 287,
            "description": "TikTok (max 180s, 287MB)",
        },
        "youtube_shorts": {
            "width": 1080, "height": 1920, "fps": 30,
            "max_duration": 60, "crf": 20,
            "codec": "libx264", "audio_bitrate": "192k",
            "target_lufs": -14, "max_file_mb": 256000,
            "description": "YouTube Shorts (max 60s)",
        },
        "instagram_reels": {
            "width": 1080, "height": 1920, "fps": 30,
            "max_duration": 90, "crf": 23,
            "codec": "libx264", "audio_bitrate": "128k",
            "target_lufs": -16, "max_file_mb": 4096,
            "description": "Instagram Reels (max 90s, 4GB)",
        },
        "twitter": {
            "width": 1080, "height": 1920, "fps": 30,
            "max_duration": 140, "crf": 25,
            "codec": "libx264", "audio_bitrate": "128k",
            "target_lufs": -16, "max_file_mb": 512,
            "description": "Twitter/X (max 140s, 512MB)",
        },
    }

    # Local LLM (Ollama)
    LLM_ENABLED: bool = True
    LLM_OLLAMA_URL: str = "http://127.0.0.1:11434"
    LLM_MODEL: str = "llama3.2"
    LLM_TIMEOUT: int = 120
    LLM_MAX_CONCURRENT: int = 3

    class Config:
        env_prefix = "FORGE_"
        env_file = Path(__file__).parent.parent.parent.parent / ".env"  # apps/forge-engine/.env
        case_sensitive = True
        # Tolerate FORGE_* keys that aren't Settings fields (e.g. FORGE_REQUIRE_AUTH,
        # read directly from the environment by core/auth.py). Without this, such a
        # line in .env makes pydantic-settings raise extra_forbidden and the whole
        # engine fails to import.
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories
        self.LIBRARY_PATH.mkdir(parents=True, exist_ok=True)
        self.TEMP_PATH.mkdir(parents=True, exist_ok=True)

        # Update database path if library path changed
        if "LIBRARY_PATH" in kwargs:
            self.DATABASE_PATH = self.LIBRARY_PATH / "forge.db"


# Override paths from environment
if os.environ.get("FORGE_LIBRARY_PATH"):
    _library_path = Path(os.environ["FORGE_LIBRARY_PATH"])
    settings = Settings(
        LIBRARY_PATH=_library_path,
        DATABASE_PATH=_library_path / "forge.db",
        TEMP_PATH=_library_path / ".temp",
    )
else:
    settings = Settings()

# Apply force CPU if specified
if os.environ.get("FORGE_FORCE_CPU"):
    settings.FORCE_CPU = True
    settings.WHISPER_DEVICE = "cpu"
    settings.WHISPER_COMPUTE_TYPE = "float32"





