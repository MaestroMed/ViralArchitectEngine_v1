"""Sound Design Service.

Provides SFX library, auto-ducking, and LUFS normalization for viral clips.

Features:
- Built-in SFX library (whoosh, pop, ding, swoosh)
- Auto-duck: automatically lower music when speech is detected
- LUFS normalization: ensure consistent loudness across clips
- Audio mixing and layering

Usage:
    from forge_engine.services.sound_design import SoundDesignService

    sound = SoundDesignService()
    await sound.apply_sound_design(clip_path, output_path, config)
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SFXCategory(StrEnum):
    """Categories of sound effects."""
    TRANSITION = "transition"
    NOTIFICATION = "notification"
    UI = "ui"
    IMPACT = "impact"
    AMBIENCE = "ambience"
    REACTION = "reaction"


@dataclass
class SFXAsset:
    """A sound effect asset."""
    id: str
    name: str
    category: SFXCategory
    filename: str
    duration: float
    tags: list[str] = field(default_factory=list)

    # Recommended usage
    recommended_volume: float = 1.0
    recommended_offset: float = 0.0  # Offset from trigger point


@dataclass
class SFXTrigger:
    """A trigger point for a sound effect."""
    time: float
    sfx_id: str
    volume: float = 1.0
    fade_in: float = 0.0
    fade_out: float = 0.0


@dataclass
class AudioTrack:
    """An audio track in the mix."""
    id: str
    type: str  # "voice", "music", "sfx", "ambient"
    path: str
    volume: float = 1.0
    start_time: float = 0.0
    end_time: float | None = None
    duck_priority: int = 0  # Higher = more important, less ducking


@dataclass
class SoundDesignConfig:
    """Configuration for sound design processing."""
    # LUFS normalization
    target_lufs: float = -14.0  # Spotify/YouTube standard
    max_true_peak: float = -1.0

    # Auto-duck settings
    duck_enabled: bool = True
    duck_threshold: float = -30.0  # dB threshold to trigger ducking
    duck_amount: float = -12.0  # How much to duck (dB)
    duck_attack: float = 0.1  # Seconds
    duck_release: float = 0.5  # Seconds

    # Music settings
    music_volume: float = 0.3  # Default music volume (0-1)
    music_fade_in: float = 0.5
    music_fade_out: float = 1.0

    # Master settings
    master_volume: float = 1.0
    limiter_enabled: bool = True


class SFXLibrary:
    """Built-in sound effects library."""

    # Default SFX assets (can be expanded with custom assets)
    BUILT_IN_SFX: list[dict[str, Any]] = [
        # Transitions
        {
            "id": "whoosh_fast",
            "name": "Whoosh Fast",
            "category": SFXCategory.TRANSITION,
            "filename": "whoosh_fast.wav",
            "duration": 0.5,
            "tags": ["transition", "fast", "swoosh"],
        },
        {
            "id": "whoosh_slow",
            "name": "Whoosh Slow",
            "category": SFXCategory.TRANSITION,
            "filename": "whoosh_slow.wav",
            "duration": 0.8,
            "tags": ["transition", "slow", "smooth"],
        },
        {
            "id": "swoosh_cinematic",
            "name": "Swoosh Cinematic",
            "category": SFXCategory.TRANSITION,
            "filename": "swoosh_cinematic.wav",
            "duration": 1.0,
            "tags": ["transition", "cinematic", "epic"],
        },

        # Notifications
        {
            "id": "pop_bright",
            "name": "Pop Bright",
            "category": SFXCategory.NOTIFICATION,
            "filename": "pop_bright.wav",
            "duration": 0.3,
            "tags": ["pop", "bright", "notification"],
        },
        {
            "id": "ding_success",
            "name": "Ding Success",
            "category": SFXCategory.NOTIFICATION,
            "filename": "ding_success.wav",
            "duration": 0.5,
            "tags": ["ding", "success", "positive"],
        },
        {
            "id": "notification_modern",
            "name": "Notification Modern",
            "category": SFXCategory.NOTIFICATION,
            "filename": "notification_modern.wav",
            "duration": 0.4,
            "tags": ["notification", "modern", "clean"],
        },

        # UI sounds
        {
            "id": "click_soft",
            "name": "Click Soft",
            "category": SFXCategory.UI,
            "filename": "click_soft.wav",
            "duration": 0.1,
            "tags": ["click", "soft", "ui"],
        },
        {
            "id": "hover_subtle",
            "name": "Hover Subtle",
            "category": SFXCategory.UI,
            "filename": "hover_subtle.wav",
            "duration": 0.15,
            "tags": ["hover", "subtle", "ui"],
        },

        # Impacts
        {
            "id": "impact_bass",
            "name": "Impact Bass",
            "category": SFXCategory.IMPACT,
            "filename": "impact_bass.wav",
            "duration": 0.6,
            "tags": ["impact", "bass", "heavy"],
        },
        {
            "id": "impact_cinematic",
            "name": "Impact Cinematic",
            "category": SFXCategory.IMPACT,
            "filename": "impact_cinematic.wav",
            "duration": 1.2,
            "tags": ["impact", "cinematic", "dramatic"],
        },
        {
            "id": "hit_punch",
            "name": "Hit Punch",
            "category": SFXCategory.IMPACT,
            "filename": "hit_punch.wav",
            "duration": 0.3,
            "tags": ["hit", "punch", "action"],
        },

        # Reactions
        {
            "id": "laugh_track",
            "name": "Laugh Track",
            "category": SFXCategory.REACTION,
            "filename": "laugh_track.wav",
            "duration": 2.0,
            "tags": ["laugh", "comedy", "reaction"],
        },
        {
            "id": "suspense_hit",
            "name": "Suspense Hit",
            "category": SFXCategory.REACTION,
            "filename": "suspense_hit.wav",
            "duration": 1.5,
            "tags": ["suspense", "dramatic", "tension"],
        },
        {
            "id": "victory_fanfare",
            "name": "Victory Fanfare",
            "category": SFXCategory.REACTION,
            "filename": "victory_fanfare.wav",
            "duration": 2.0,
            "tags": ["victory", "win", "celebration"],
        },
    ]

    def __init__(self, custom_sfx_path: str | None = None):
        self.custom_sfx_path = Path(custom_sfx_path) if custom_sfx_path else None
        self._assets: dict[str, SFXAsset] = {}
        self._load_library()

    def _load_library(self):
        """Load SFX library."""
        # Load built-in SFX
        for sfx_data in self.BUILT_IN_SFX:
            asset = SFXAsset(
                id=sfx_data["id"],
                name=sfx_data["name"],
                category=sfx_data["category"],
                filename=sfx_data["filename"],
                duration=sfx_data["duration"],
                tags=sfx_data.get("tags", []),
            )
            self._assets[asset.id] = asset

        # Load custom SFX if path provided
        if self.custom_sfx_path and self.custom_sfx_path.exists():
            self._load_custom_sfx()

        logger.info("SFX library loaded: %d assets", len(self._assets))

    def _load_custom_sfx(self):
        """Load custom SFX from directory."""
        manifest_path = self.custom_sfx_path / "manifest.json"

        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)

                for sfx_data in manifest.get("assets", []):
                    asset = SFXAsset(
                        id=sfx_data["id"],
                        name=sfx_data["name"],
                        category=SFXCategory(sfx_data.get("category", "reaction")),
                        filename=sfx_data["filename"],
                        duration=sfx_data.get("duration", 1.0),
                        tags=sfx_data.get("tags", []),
                    )
                    self._assets[asset.id] = asset

            except Exception as e:
                logger.warning("Failed to load custom SFX manifest: %s", e)

    def get_asset(self, sfx_id: str) -> SFXAsset | None:
        """Get an SFX asset by ID."""
        return self._assets.get(sfx_id)

    def search(
        self,
        query: str = "",
        category: SFXCategory | None = None,
        tags: list[str] | None = None,
    ) -> list[SFXAsset]:
        """Search for SFX assets."""
        results = []

        for asset in self._assets.values():
            # Category filter
            if category and asset.category != category:
                continue

            # Tag filter
            if tags:
                if not any(tag in asset.tags for tag in tags):
                    continue

            # Query filter
            if query:
                query_lower = query.lower()
                if (query_lower not in asset.name.lower() and
                    query_lower not in asset.id.lower() and
                    not any(query_lower in tag for tag in asset.tags)):
                    continue

            results.append(asset)

        return results

    def get_by_category(self, category: SFXCategory) -> list[SFXAsset]:
        """Get all SFX in a category."""
        return [a for a in self._assets.values() if a.category == category]

    def list_all(self) -> list[SFXAsset]:
        """List all SFX assets."""
        return list(self._assets.values())


class SoundDesignService:
    """Service for applying sound design to clips."""

    def __init__(self):
        self.library = SFXLibrary()
        self.default_config = SoundDesignConfig()

    async def apply_sound_design(
        self,
        input_path: str,
        output_path: str,
        config: SoundDesignConfig | None = None,
        music_path: str | None = None,
        sfx_triggers: list[SFXTrigger] | None = None,
        progress_callback: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Apply full sound design processing to a clip.

        Args:
            input_path: Input video/audio path
            output_path: Output path
            config: Sound design configuration
            music_path: Optional background music path
            sfx_triggers: Optional list of SFX triggers
            progress_callback: Progress callback

        Returns:
            Result dictionary with loudness stats
        """
        cfg = config or self.default_config

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._apply_sound_design_sync(
                input_path, output_path, cfg,
                music_path, sfx_triggers, progress_callback
            )
        )

    def _apply_sound_design_sync(
        self,
        input_path: str,
        output_path: str,
        config: SoundDesignConfig,
        music_path: str | None,
        sfx_triggers: list[SFXTrigger] | None,
        progress_callback: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Synchronous sound design processing."""
        if progress_callback:
            progress_callback(5)

        # Analyze input loudness
        input_loudness = self._analyze_loudness(input_path)

        if progress_callback:
            progress_callback(20)

        # Build FFmpeg filter chain
        filters = []

        # Step 1: Auto-duck if music is added
        if music_path and config.duck_enabled:
            # This is complex in FFmpeg - simplified version
            logger.info("Auto-duck enabled for music")

        # Step 2: LUFS normalization
        loudnorm_filter = self._build_loudnorm_filter(
            input_loudness,
            config.target_lufs,
            config.max_true_peak,
        )
        filters.append(loudnorm_filter)

        if progress_callback:
            progress_callback(40)

        # Step 3: Limiter
        if config.limiter_enabled:
            filters.append(f"alimiter=limit={config.max_true_peak}dB:attack=5:release=50")

        # Step 4: Master volume
        if config.master_volume != 1.0:
            filters.append(f"volume={config.master_volume}")

        # Build command
        filter_chain = ",".join(filters) if filters else "anull"

        # If we have music, mix it
        if music_path:
            self._mix_with_music(
                input_path, music_path, output_path,
                filter_chain, config, progress_callback
            )
        else:
            self._process_audio(
                input_path, output_path, filter_chain, progress_callback
            )

        if progress_callback:
            progress_callback(90)

        # Analyze output loudness
        output_loudness = self._analyze_loudness(output_path)

        if progress_callback:
            progress_callback(100)

        return {
            "success": True,
            "input_loudness": input_loudness,
            "output_loudness": output_loudness,
            "config": {
                "target_lufs": config.target_lufs,
                "duck_enabled": config.duck_enabled,
            },
        }

    def _analyze_loudness(self, audio_path: str) -> dict[str, float]:
        """Analyze audio loudness using FFmpeg."""
        try:
            cmd = [
                "ffmpeg", "-i", audio_path,
                "-af", "loudnorm=print_format=json",
                "-f", "null", "-"
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )

            # Parse loudness stats from stderr
            output = result.stderr

            # Find JSON block
            import re
            json_match = re.search(r'\{[^}]+\}', output, re.DOTALL)

            if json_match:
                data = json.loads(json_match.group())
                return {
                    "input_i": float(data.get("input_i", -23)),
                    "input_tp": float(data.get("input_tp", -1)),
                    "input_lra": float(data.get("input_lra", 7)),
                    "input_thresh": float(data.get("input_thresh", -35)),
                }

        except Exception as e:
            logger.warning("Loudness analysis failed: %s", e)

        # Return defaults
        return {
            "input_i": -23.0,
            "input_tp": -1.0,
            "input_lra": 7.0,
            "input_thresh": -35.0,
        }

    def _build_loudnorm_filter(
        self,
        loudness: dict[str, float],
        target_lufs: float,
        max_tp: float,
    ) -> str:
        """Build FFmpeg loudnorm filter for LUFS normalization."""
        return (
            f"loudnorm=I={target_lufs}:TP={max_tp}:LRA=11:"
            f"measured_I={loudness['input_i']}:"
            f"measured_TP={loudness['input_tp']}:"
            f"measured_LRA={loudness['input_lra']}:"
            f"measured_thresh={loudness['input_thresh']}:"
            f"linear=true:print_format=summary"
        )

    def _process_audio(
        self,
        input_path: str,
        output_path: str,
        filter_chain: str,
        progress_callback: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Process audio with filter chain."""
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", filter_chain,
            "-c:v", "copy",  # Copy video if present
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                logger.error("FFmpeg failed: %s", result.stderr)
                return {"success": False, "error": result.stderr}

            return {"success": True}

        except Exception as e:
            logger.error("Audio processing failed: %s", e)
            return {"success": False, "error": str(e)}

    def _mix_with_music(
        self,
        voice_path: str,
        music_path: str,
        output_path: str,
        voice_filter: str,
        config: SoundDesignConfig,
        progress_callback: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Mix voice with background music including auto-duck."""
        # Get voice duration
        try:
            from forge_engine.core.config import settings as _s
            _ffprobe = getattr(_s, "FFPROBE_PATH", "ffprobe")
            probe_cmd = [
                _ffprobe, "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0", voice_path
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
            duration = float(result.stdout.strip())
        except Exception:
            duration = 60.0

        # Build complex filter for mixing with ducking
        # [0:a] = voice, [1:a] = music
        music_vol = config.music_volume

        # Simplified ducking using sidechaincompress
        filter_complex = (
            # Apply voice filters
            f"[0:a]{voice_filter}[voice];"
            # Prepare music (fade in/out, volume)
            f"[1:a]afade=t=in:st=0:d={config.music_fade_in},"
            f"afade=t=out:st={duration - config.music_fade_out}:d={config.music_fade_out},"
            f"volume={music_vol}[music];"
            # Sidechain compress music with voice (auto-duck)
            f"[music][voice]sidechaincompress="
            f"threshold={config.duck_threshold}dB:"
            f"ratio=4:attack={config.duck_attack * 1000}:"
            f"release={config.duck_release * 1000}[ducked];"
            # Mix voice and ducked music
            f"[voice][ducked]amix=inputs=2:duration=first[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", voice_path,
            "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "0:v?",  # Keep video if present
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                logger.error("Music mixing failed: %s", result.stderr)
                return {"success": False, "error": result.stderr}

            return {"success": True, "with_music": True}

        except Exception as e:
            logger.error("Music mixing failed: %s", e)
            return {"success": False, "error": str(e)}

    async def normalize_lufs(
        self,
        input_path: str,
        output_path: str,
        target_lufs: float = -14.0,
        max_true_peak: float = -1.0,
    ) -> dict[str, Any]:
        """Quick LUFS normalization only."""
        config = SoundDesignConfig(
            target_lufs=target_lufs,
            max_true_peak=max_true_peak,
            duck_enabled=False,
            limiter_enabled=True,
        )

        return await self.apply_sound_design(
            input_path, output_path, config
        )

    def get_sfx_library(self) -> SFXLibrary:
        """Get the SFX library."""
        return self.library

    def get_recommended_sfx(
        self,
        clip_type: str,
    ) -> list[SFXAsset]:
        """Get recommended SFX for a clip type."""
        recommendations = {
            "intro": [SFXCategory.TRANSITION, SFXCategory.IMPACT],
            "outro": [SFXCategory.TRANSITION],
            "reaction": [SFXCategory.REACTION],
            "highlight": [SFXCategory.IMPACT, SFXCategory.NOTIFICATION],
            "fail": [SFXCategory.REACTION],
            "victory": [SFXCategory.REACTION, SFXCategory.NOTIFICATION],
        }

        categories = recommendations.get(clip_type, [SFXCategory.TRANSITION])

        sfx = []
        for cat in categories:
            sfx.extend(self.library.get_by_category(cat))

        return sfx
