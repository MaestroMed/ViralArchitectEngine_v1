"""Transcription Provider Architecture.

Abstraction layer for switching between transcription backends:
- Local: faster-whisper on GPU (default, free)
- OpenAI API: OpenAI Whisper API (fast, paid)
- Deepgram API: Deepgram Nova-2 (fastest, paid)

Usage:
    provider = TranscriptionProviderManager.get_instance()
    result = await provider.transcribe(audio_path, language="fr")
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProviderType(StrEnum):
    """Available transcription providers."""
    LOCAL = "local"
    LOCAL_ALIGNED = "local_aligned"  # Local + WhisperX alignment
    WHISPERX = "whisperx"  # Full WhisperX pipeline
    OPENAI = "openai"
    DEEPGRAM = "deepgram"


@dataclass
class TranscriptionConfig:
    """Configuration for transcription."""
    language: str = "fr"
    word_timestamps: bool = True
    initial_prompt: str | None = None
    custom_dictionary: list[str] | None = None
    model_override: str | None = None
    turbo_mode: bool = True


@dataclass
class TranscriptionResult:
    """Unified transcription result."""
    language: str
    language_probability: float
    duration: float
    segments: list[dict[str, Any]]
    text: str
    provider: ProviderType
    cost: float | None = None  # For paid APIs


class TranscriptionProvider(ABC):
    """Abstract base class for transcription providers."""

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig,
        progress_callback: Callable[..., Any] | None = None
    ) -> TranscriptionResult:
        """Transcribe audio file."""
        pass

    @abstractmethod
    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate cost for transcription (0 for local)."""
        pass


class LocalTranscriptionProvider(TranscriptionProvider):
    """Local transcription using faster-whisper on GPU."""

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.LOCAL

    def is_available(self) -> bool:
        try:
            from forge_engine.services.transcription import TranscriptionService
            return TranscriptionService.get_instance().is_available()
        except Exception:
            return False

    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig,
        progress_callback: Callable[..., Any] | None = None
    ) -> TranscriptionResult:
        from forge_engine.services.transcription import TranscriptionService

        service = TranscriptionService.get_instance()
        result = await service.transcribe(
            audio_path=audio_path,
            language=config.language,
            word_timestamps=config.word_timestamps,
            initial_prompt=config.initial_prompt,
            custom_dictionary=config.custom_dictionary,
            progress_callback=progress_callback,
            model_override=config.model_override,
            turbo_mode=config.turbo_mode
        )

        return TranscriptionResult(
            language=result.get("language", config.language),
            language_probability=result.get("language_probability", 1.0),
            duration=result.get("duration", 0),
            segments=result.get("segments", []),
            text=result.get("text", ""),
            provider=ProviderType.LOCAL,
            cost=0.0
        )

    def estimate_cost(self, duration_seconds: float) -> float:
        return 0.0  # Free (just electricity)


class OpenAITranscriptionProvider(TranscriptionProvider):
    """OpenAI Whisper API transcription.

    Pricing (as of 2025):
    - whisper-1: $0.006 per minute ($0.36/hour)

    For a 3h VOD: ~$1.08
    """

    PRICE_PER_MINUTE = 0.006

    def __init__(self):
        self._api_key = os.environ.get("OPENAI_API_KEY")

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.OPENAI

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import openai
            return True
        except ImportError:
            return False

    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig,
        progress_callback: Callable[..., Any] | None = None
    ) -> TranscriptionResult:
        if not self.is_available():
            raise RuntimeError("OpenAI API not available. Set OPENAI_API_KEY.")

        import openai

        if progress_callback:
            progress_callback(5)

        logger.info("Transcribing with OpenAI Whisper API: %s", audio_path)

        client = openai.OpenAI(api_key=self._api_key)

        # OpenAI has a 25MB limit per file, may need to chunk
        file_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)

        if file_size_mb > 24:
            logger.warning(
                "File too large for OpenAI (%.1f MB > 25 MB), falling back to local",
                file_size_mb
            )
            return await LocalTranscriptionProvider().transcribe(
                audio_path, config, progress_callback
            )

        if progress_callback:
            progress_callback(10)

        # Build prompt from dictionary
        prompt = config.initial_prompt or ""
        if config.custom_dictionary:
            prompt = ", ".join(config.custom_dictionary[:50]) + ". " + prompt

        with open(audio_path, "rb") as audio_file:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=config.language,
                    prompt=prompt[:224] if prompt else None,  # OpenAI limit
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"] if config.word_timestamps else ["segment"]
                )
            )

        if progress_callback:
            progress_callback(90)

        # Convert OpenAI response to unified format
        segments = []
        for i, seg in enumerate(response.segments or []):
            seg_data = {
                "id": i,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            }

            # Add word timestamps if available
            if config.word_timestamps and hasattr(response, 'words') and response.words:
                # Filter words for this segment
                seg_words = [
                    w for w in response.words
                    if seg.start <= w.start < seg.end
                ]
                if seg_words:
                    seg_data["words"] = [
                        {
                            "word": w.word,
                            "start": w.start,
                            "end": w.end,
                            "confidence": 1.0  # OpenAI doesn't return confidence
                        }
                        for w in seg_words
                    ]

            segments.append(seg_data)

        if progress_callback:
            progress_callback(100)

        duration = response.duration if hasattr(response, 'duration') else 0
        cost = self.estimate_cost(duration)

        logger.info(
            "OpenAI transcription complete: %d segments, %.1fs, $%.2f",
            len(segments), duration, cost
        )

        return TranscriptionResult(
            language=response.language if hasattr(response, 'language') else config.language,
            language_probability=1.0,
            duration=duration,
            segments=segments,
            text=response.text,
            provider=ProviderType.OPENAI,
            cost=cost
        )

    def estimate_cost(self, duration_seconds: float) -> float:
        minutes = duration_seconds / 60
        return minutes * self.PRICE_PER_MINUTE


class LocalAlignedTranscriptionProvider(TranscriptionProvider):
    """Local transcription with WhisperX post-alignment.

    Combines faster-whisper's speed with WhisperX's precise alignment.
    Best of both worlds: fast transcription + frame-accurate word timestamps.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.LOCAL_ALIGNED

    def is_available(self) -> bool:
        try:
            from forge_engine.services.transcription import TranscriptionService
            from forge_engine.services.whisperx_alignment import WhisperXAligner

            local_ok = TranscriptionService.get_instance().is_available()
            aligner_ok = WhisperXAligner.get_instance().is_available()

            return local_ok and aligner_ok
        except Exception:
            return False

    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig,
        progress_callback: Callable[..., Any] | None = None
    ) -> TranscriptionResult:
        from forge_engine.services.transcription import TranscriptionService
        from forge_engine.services.whisperx_alignment import WhisperXAligner

        # Wrapper for progress that splits between transcription and alignment
        def trans_progress(pct: float):
            if progress_callback:
                # First 60% is transcription
                progress_callback(pct * 0.6)

        def align_progress(pct: float):
            if progress_callback:
                # Last 40% is alignment
                progress_callback(60 + pct * 0.4)

        # Step 1: Fast transcription with faster-whisper
        service = TranscriptionService.get_instance()
        result = await service.transcribe(
            audio_path=audio_path,
            language=config.language,
            word_timestamps=True,  # We need these for alignment
            initial_prompt=config.initial_prompt,
            custom_dictionary=config.custom_dictionary,
            progress_callback=trans_progress,
            model_override=config.model_override,
            turbo_mode=config.turbo_mode
        )

        # Step 2: WhisperX alignment for precise timestamps
        aligner = WhisperXAligner.get_instance()
        aligned = await aligner.align_transcription(
            audio_path=audio_path,
            transcription=result,
            language=config.language,
            progress_callback=align_progress,
        )

        return TranscriptionResult(
            language=aligned.get("language", config.language),
            language_probability=aligned.get("language_probability", 1.0),
            duration=aligned.get("duration", 0),
            segments=aligned.get("segments", []),
            text=aligned.get("text", ""),
            provider=ProviderType.LOCAL_ALIGNED,
            cost=0.0
        )

    def estimate_cost(self, duration_seconds: float) -> float:
        return 0.0  # Free (just electricity and time)


class WhisperXTranscriptionProvider(TranscriptionProvider):
    """Full WhisperX transcription + alignment pipeline.

    Uses WhisperX for both transcription and alignment in a single pass.
    Slightly slower than LOCAL_ALIGNED but potentially more accurate
    for edge cases where alignment might fail.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.WHISPERX

    def is_available(self) -> bool:
        try:
            from forge_engine.services.whisperx_alignment import WhisperXTranscriber
            return WhisperXTranscriber.get_instance().is_available()
        except Exception:
            return False

    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig,
        progress_callback: Callable[..., Any] | None = None
    ) -> TranscriptionResult:
        from forge_engine.services.whisperx_alignment import WhisperXTranscriber

        transcriber = WhisperXTranscriber.get_instance()
        result = await transcriber.transcribe_and_align(
            audio_path=audio_path,
            language=config.language,
            model_name=config.model_override or "large-v3",
            with_diarization=False,
            progress_callback=progress_callback,
        )

        return TranscriptionResult(
            language=result.get("language", config.language),
            language_probability=result.get("language_probability", 1.0),
            duration=result.get("duration", 0),
            segments=result.get("segments", []),
            text=result.get("text", ""),
            provider=ProviderType.WHISPERX,
            cost=0.0
        )

    def estimate_cost(self, duration_seconds: float) -> float:
        return 0.0  # Free


class DeepgramTranscriptionProvider(TranscriptionProvider):
    """Deepgram Nova-2 API transcription.

    Pricing (as of 2025):
    - Nova-2: $0.0043 per minute ($0.258/hour)

    For a 3h VOD: ~$0.77

    Generally faster than OpenAI with similar quality.
    """

    PRICE_PER_MINUTE = 0.0043

    def __init__(self):
        self._api_key = os.environ.get("DEEPGRAM_API_KEY")

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DEEPGRAM

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            from deepgram import DeepgramClient
            return True
        except ImportError:
            return False

    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig,
        progress_callback: Callable[..., Any] | None = None
    ) -> TranscriptionResult:
        if not self.is_available():
            raise RuntimeError("Deepgram API not available. Set DEEPGRAM_API_KEY.")

        from deepgram import DeepgramClient, FileSource, PrerecordedOptions

        if progress_callback:
            progress_callback(5)

        logger.info("Transcribing with Deepgram Nova-2: %s", audio_path)

        client = DeepgramClient(self._api_key)

        with open(audio_path, "rb") as audio_file:
            source = FileSource(buffer=audio_file.read())

        if progress_callback:
            progress_callback(10)

        options = PrerecordedOptions(
            model="nova-2",
            language=config.language,
            smart_format=True,
            punctuate=True,
            paragraphs=True,
            diarize=False,
            filler_words=False,
        )

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.listen.rest.v("1").transcribe_file(source, options)
        )

        if progress_callback:
            progress_callback(90)

        # Convert Deepgram response to unified format
        segments = []
        alt = response.results.channels[0].alternatives[0]

        if hasattr(alt, 'paragraphs') and alt.paragraphs:
            # Use paragraphs as segments
            for i, para in enumerate(alt.paragraphs.paragraphs):
                seg_data = {
                    "id": i,
                    "start": para.start,
                    "end": para.end,
                    "text": " ".join(s.text for s in para.sentences),
                }

                if config.word_timestamps and hasattr(alt, 'words'):
                    seg_words = [
                        w for w in alt.words
                        if para.start <= w.start < para.end
                    ]
                    if seg_words:
                        seg_data["words"] = [
                            {
                                "word": w.word,
                                "start": w.start,
                                "end": w.end,
                                "confidence": w.confidence
                            }
                            for w in seg_words
                        ]

                segments.append(seg_data)
        else:
            # Fallback: use word groups as segments
            words = alt.words if hasattr(alt, 'words') else []
            current_segment = {"id": 0, "start": 0, "end": 0, "text": "", "words": []}

            for word in words:
                if current_segment["end"] > 0 and word.start - current_segment["end"] > 1.5:
                    # Gap detected, start new segment
                    if current_segment["text"]:
                        segments.append(current_segment)
                    current_segment = {
                        "id": len(segments),
                        "start": word.start,
                        "end": word.end,
                        "text": word.word,
                        "words": [{"word": word.word, "start": word.start, "end": word.end, "confidence": word.confidence}]
                    }
                else:
                    if not current_segment["text"]:
                        current_segment["start"] = word.start
                    current_segment["end"] = word.end
                    current_segment["text"] += " " + word.word if current_segment["text"] else word.word
                    current_segment["words"].append({
                        "word": word.word, "start": word.start, "end": word.end, "confidence": word.confidence
                    })

            if current_segment["text"]:
                segments.append(current_segment)

        if progress_callback:
            progress_callback(100)

        duration = response.metadata.duration if hasattr(response.metadata, 'duration') else 0
        cost = self.estimate_cost(duration)

        logger.info(
            "Deepgram transcription complete: %d segments, %.1fs, $%.2f",
            len(segments), duration, cost
        )

        return TranscriptionResult(
            language=config.language,
            language_probability=1.0,
            duration=duration,
            segments=segments,
            text=alt.transcript,
            provider=ProviderType.DEEPGRAM,
            cost=cost
        )

    def estimate_cost(self, duration_seconds: float) -> float:
        minutes = duration_seconds / 60
        return minutes * self.PRICE_PER_MINUTE


# Need this import for OpenAI/Deepgram providers
import asyncio


class TranscriptionProviderManager:
    """Manages transcription providers with automatic fallback.

    Priority:
    1. Configured provider (if available)
    2. Local (if GPU available)
    3. OpenAI (if API key set)
    4. Deepgram (if API key set)

    Usage:
        manager = TranscriptionProviderManager.get_instance()
        result = await manager.transcribe(audio_path, language="fr")
    """

    _instance: TranscriptionProviderManager | None = None

    def __init__(self):
        self._providers: dict[ProviderType, TranscriptionProvider] = {}
        self._default_provider: ProviderType = ProviderType.LOCAL
        self._initialize_providers()

    @classmethod
    def get_instance(cls) -> TranscriptionProviderManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_providers(self):
        """Initialize all available providers."""
        # Local provider (always available if faster-whisper installed)
        local = LocalTranscriptionProvider()
        if local.is_available():
            self._providers[ProviderType.LOCAL] = local
            logger.info("Local transcription provider available")

        # Local + WhisperX alignment (best for karaoke subtitles)
        local_aligned = LocalAlignedTranscriptionProvider()
        if local_aligned.is_available():
            self._providers[ProviderType.LOCAL_ALIGNED] = local_aligned
            logger.info("Local+WhisperX aligned transcription provider available")
            # If WhisperX is available, use aligned as default for better quality
            self._default_provider = ProviderType.LOCAL_ALIGNED

        # Full WhisperX pipeline
        whisperx_provider = WhisperXTranscriptionProvider()
        if whisperx_provider.is_available():
            self._providers[ProviderType.WHISPERX] = whisperx_provider
            logger.info("WhisperX transcription provider available")

        # OpenAI provider
        openai_provider = OpenAITranscriptionProvider()
        if openai_provider.is_available():
            self._providers[ProviderType.OPENAI] = openai_provider
            logger.info("OpenAI transcription provider available")

        # Deepgram provider
        deepgram = DeepgramTranscriptionProvider()
        if deepgram.is_available():
            self._providers[ProviderType.DEEPGRAM] = deepgram
            logger.info("Deepgram transcription provider available")

        logger.info(
            "Transcription providers initialized: %s (default: %s)",
            list(self._providers.keys()),
            self._default_provider
        )

    @property
    def available_providers(self) -> list[ProviderType]:
        """Get list of available providers."""
        return list(self._providers.keys())

    @property
    def default_provider(self) -> ProviderType:
        """Get default provider."""
        return self._default_provider

    @default_provider.setter
    def default_provider(self, provider: ProviderType):
        """Set default provider."""
        if provider in self._providers:
            self._default_provider = provider
            logger.info("Default transcription provider set to: %s", provider)
        else:
            raise ValueError(f"Provider {provider} is not available")

    def get_provider(self, provider_type: ProviderType) -> TranscriptionProvider | None:
        """Get a specific provider."""
        return self._providers.get(provider_type)

    def estimate_cost(
        self,
        duration_seconds: float,
        provider: ProviderType | None = None
    ) -> dict[ProviderType, float]:
        """Estimate costs for transcription across providers."""
        costs = {}

        for ptype, provider_instance in self._providers.items():
            if provider is None or ptype == provider:
                costs[ptype] = provider_instance.estimate_cost(duration_seconds)

        return costs

    async def transcribe(
        self,
        audio_path: str,
        config: TranscriptionConfig | None = None,
        provider: ProviderType | None = None,
        progress_callback: Callable[..., Any] | None = None,
        fallback: bool = True
    ) -> TranscriptionResult:
        """Transcribe audio using configured or specified provider.

        Args:
            audio_path: Path to audio file
            config: Transcription configuration
            provider: Specific provider to use (default: configured default)
            progress_callback: Progress callback
            fallback: Whether to fallback to other providers on failure

        Returns:
            TranscriptionResult
        """
        if config is None:
            config = TranscriptionConfig()

        # Determine provider to use
        target_provider = provider or self._default_provider

        # Build fallback chain
        fallback_chain = [target_provider]
        if fallback:
            # Fallback order: prefer aligned local, then basic local, then cloud
            for ptype in [
                ProviderType.LOCAL_ALIGNED,
                ProviderType.LOCAL,
                ProviderType.WHISPERX,
                ProviderType.OPENAI,
                ProviderType.DEEPGRAM
            ]:
                if ptype not in fallback_chain and ptype in self._providers:
                    fallback_chain.append(ptype)

        # Try providers in order
        last_error = None
        for ptype in fallback_chain:
            if ptype not in self._providers:
                continue

            try:
                logger.info("Attempting transcription with provider: %s", ptype)
                return await self._providers[ptype].transcribe(
                    audio_path, config, progress_callback
                )
            except Exception as e:
                logger.warning("Provider %s failed: %s", ptype, e)
                last_error = e
                continue

        raise RuntimeError(f"All transcription providers failed. Last error: {last_error}")

    def get_status(self) -> dict:
        """Get provider manager status."""
        return {
            "available_providers": [p.value for p in self.available_providers],
            "default_provider": self._default_provider.value,
            "providers": {
                ptype.value: {
                    "available": provider.is_available(),
                    "estimated_cost_per_hour": provider.estimate_cost(3600)
                }
                for ptype, provider in self._providers.items()
            }
        }
