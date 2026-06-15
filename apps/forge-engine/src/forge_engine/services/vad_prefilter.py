"""Voice Activity Detection pre-filter using Silero VAD.

Pre-filters audio to detect speech segments BEFORE transcription.
This saves significant processing time by skipping:
- Silences
- Music/intro sections
- Pure game audio without commentary

Gain: 30-50% reduction in transcription time for typical streams.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SpeechSegment:
    """A detected speech segment."""
    start: float  # seconds
    end: float    # seconds
    confidence: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class VADResult:
    """Result of VAD pre-filtering."""
    segments: list[SpeechSegment]
    total_duration: float  # Total audio duration
    speech_duration: float  # Total speech duration
    speech_ratio: float  # Ratio of speech to total

    @property
    def segments_for_transcription(self) -> list[tuple[float, float]]:
        """Get (start, end) tuples for transcription."""
        return [(s.start, s.end) for s in self.segments]

    @property
    def time_saved_ratio(self) -> float:
        """How much time we save by skipping non-speech."""
        return 1.0 - self.speech_ratio


class VADPrefilterService:
    """Pre-filter audio using Silero VAD for faster transcription.

    Uses Silero VAD (MIT license, runs on CPU) to detect speech segments.
    This is much faster than Whisper's built-in VAD and can be run
    in parallel with downloads or other operations.
    """

    _instance: VADPrefilterService | None = None
    _model = None
    _utils = None

    def __init__(self):
        self._available = False
        self._check_availability()

    @classmethod
    def get_instance(cls) -> VADPrefilterService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _check_availability(self):
        """Check if Silero VAD is available."""
        try:
            import torch
            self._available = True
            logger.info("Silero VAD available (torch installed)")
        except ImportError:
            self._available = False
            logger.warning("Silero VAD not available (torch not installed)")

    def is_available(self) -> bool:
        """Check if VAD pre-filtering is available."""
        return self._available

    def _load_model(self):
        """Load Silero VAD model (lazy loading)."""
        if self._model is not None:
            return

        if not self._available:
            raise RuntimeError("Silero VAD is not available")

        import torch

        logger.info("Loading Silero VAD model...")

        # Load Silero VAD from torch.hub
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True
        )

        self._model = model
        self._utils = utils
        logger.info("Silero VAD model loaded successfully")

    async def prefilter_audio(
        self,
        audio_path: str,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
        padding_ms: int = 200,
        merge_threshold_ms: int = 1000,
        progress_callback: Callable[..., Any] | None = None
    ) -> VADResult:
        """Pre-filter audio to detect speech segments.

        Args:
            audio_path: Path to audio file
            threshold: Speech detection threshold (0-1)
            min_speech_duration_ms: Minimum speech segment duration
            min_silence_duration_ms: Minimum silence to split segments
            padding_ms: Padding to add around speech segments
            merge_threshold_ms: Merge segments closer than this
            progress_callback: Optional progress callback

        Returns:
            VADResult with detected speech segments
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._prefilter_sync(
                audio_path, threshold, min_speech_duration_ms,
                min_silence_duration_ms, padding_ms, merge_threshold_ms,
                progress_callback
            )
        )

    def _prefilter_sync(
        self,
        audio_path: str,
        threshold: float,
        min_speech_duration_ms: int,
        min_silence_duration_ms: int,
        padding_ms: int,
        merge_threshold_ms: int,
        progress_callback: Callable[..., Any] | None
    ) -> VADResult:
        """Synchronous VAD pre-filtering."""
        self._load_model()


        if progress_callback:
            progress_callback(5)

        # Load audio
        get_speech_timestamps = self._utils[0]
        read_audio = self._utils[1]

        # Read audio at 16kHz (required by Silero)
        logger.info("Loading audio for VAD: %s", audio_path)
        wav = read_audio(audio_path, sampling_rate=16000)

        if progress_callback:
            progress_callback(20)

        total_duration = len(wav) / 16000  # seconds
        logger.info("Audio loaded: %.1f seconds", total_duration)

        # Get speech timestamps
        logger.info("Detecting speech segments (threshold=%.2f)...", threshold)
        speech_timestamps = get_speech_timestamps(
            wav,
            self._model,
            threshold=threshold,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            speech_pad_ms=padding_ms,
            return_seconds=True,
        )

        if progress_callback:
            progress_callback(80)

        # Convert to SpeechSegment objects
        segments = []
        for ts in speech_timestamps:
            segments.append(SpeechSegment(
                start=ts['start'],
                end=ts['end'],
                confidence=1.0  # Silero doesn't return confidence per segment
            ))

        # Merge close segments
        merged_segments = self._merge_segments(segments, merge_threshold_ms / 1000.0)

        # Calculate statistics
        speech_duration = sum(s.duration for s in merged_segments)
        speech_ratio = speech_duration / total_duration if total_duration > 0 else 0

        if progress_callback:
            progress_callback(100)

        result = VADResult(
            segments=merged_segments,
            total_duration=total_duration,
            speech_duration=speech_duration,
            speech_ratio=speech_ratio
        )

        logger.info(
            "VAD complete: %d segments, %.1fs speech / %.1fs total (%.1f%% speech, %.1f%% time saved)",
            len(merged_segments), speech_duration, total_duration,
            speech_ratio * 100, result.time_saved_ratio * 100
        )

        return result

    def _merge_segments(
        self,
        segments: list[SpeechSegment],
        merge_threshold: float
    ) -> list[SpeechSegment]:
        """Merge segments that are close together."""
        if not segments:
            return []

        merged = [segments[0]]

        for seg in segments[1:]:
            last = merged[-1]
            gap = seg.start - last.end

            if gap <= merge_threshold:
                # Merge with previous segment
                merged[-1] = SpeechSegment(
                    start=last.start,
                    end=seg.end,
                    confidence=(last.confidence + seg.confidence) / 2
                )
            else:
                merged.append(seg)

        return merged

    def get_transcription_chunks(
        self,
        vad_result: VADResult,
        max_chunk_duration: float = 300.0,  # 5 minutes
        min_chunk_duration: float = 10.0
    ) -> list[tuple[float, float]]:
        """Get optimized chunks for transcription.

        Combines speech segments into reasonable chunks for parallel
        transcription while respecting natural boundaries.

        Args:
            vad_result: Result from prefilter_audio
            max_chunk_duration: Maximum chunk duration
            min_chunk_duration: Minimum chunk duration

        Returns:
            List of (start, end) tuples for transcription
        """
        if not vad_result.segments:
            # No speech detected, return full audio as single chunk
            return [(0, vad_result.total_duration)]

        chunks = []
        current_start = None
        current_end = None

        for seg in vad_result.segments:
            if current_start is None:
                current_start = seg.start
                current_end = seg.end
            else:
                current_duration = current_end - current_start

                # Would adding this segment exceed max duration?
                if current_duration + seg.duration > max_chunk_duration:
                    # Save current chunk if it's long enough
                    if current_duration >= min_chunk_duration:
                        chunks.append((current_start, current_end))

                    # Start new chunk
                    current_start = seg.start
                    current_end = seg.end
                else:
                    # Extend current chunk
                    current_end = seg.end

        # Don't forget the last chunk
        if current_start is not None:
            chunks.append((current_start, current_end))

        logger.info(
            "Created %d transcription chunks from %d speech segments",
            len(chunks), len(vad_result.segments)
        )

        return chunks
