"""WhisperX Word-Level Alignment Service.

Provides frame-accurate word-level timestamps using phoneme-based forced alignment.

WhisperX improves upon faster-whisper's word timestamps by:
1. Using wav2vec2 for phoneme detection
2. Forced alignment between audio and transcript
3. Sub-frame accuracy (±10ms vs ±100ms)

This is critical for:
- Karaoke subtitles with perfect word sync
- Precise clip cutting at word boundaries
- Professional-grade caption timing

Usage:
    from forge_engine.services.whisperx_alignment import WhisperXAligner

    aligner = WhisperXAligner.get_instance()
    aligned = await aligner.align_transcription(audio_path, transcription_result)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, Optional

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


class WhisperXAligner:
    """Service for precise word-level alignment using WhisperX.

    Features:
    - Frame-accurate word timestamps (±10ms)
    - Multi-language support via language-specific wav2vec2 models
    - Speaker diarization (optional)
    - Batch processing for long files
    """

    _instance: WhisperXAligner | None = None
    _align_model = None
    _diarize_pipeline = None
    _current_language: str | None = None

    # Language to wav2vec2 model mapping
    LANGUAGE_MODELS = {
        "fr": "jonatasgrosman/wav2vec2-large-xlsr-53-french",
        "en": "jonatasgrosman/wav2vec2-large-xlsr-53-english",
        "es": "jonatasgrosman/wav2vec2-large-xlsr-53-spanish",
        "de": "jonatasgrosman/wav2vec2-large-xlsr-53-german",
        "it": "jonatasgrosman/wav2vec2-large-xlsr-53-italian",
        "pt": "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese",
        "ja": "jonatasgrosman/wav2vec2-large-xlsr-53-japanese",
        "ko": "kresnik/wav2vec2-large-xlsr-korean",
        "zh": "jonatasgrosman/wav2vec2-large-xlsr-53-chinese-zh-cn",
        "ru": "jonatasgrosman/wav2vec2-large-xlsr-53-russian",
        "pl": "jonatasgrosman/wav2vec2-large-xlsr-53-polish",
        "nl": "jonatasgrosman/wav2vec2-large-xlsr-53-dutch",
    }

    def __init__(self):
        self.device = "cuda" if self._check_cuda() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "float32"

    @classmethod
    def get_instance(cls) -> WhisperXAligner:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _check_cuda() -> bool:
        """Check if CUDA is available for WhisperX."""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def is_available(self) -> bool:
        """Check if WhisperX is available."""
        try:
            import whisperx
            return True
        except ImportError:
            logger.debug("WhisperX not installed. Run: pip install whisperx")
            return False

    def _load_align_model(self, language: str):
        """Load the alignment model for the specified language."""
        if not self.is_available():
            raise RuntimeError("WhisperX is not installed. Run: pip install whisperx")

        # Check if we need to reload for a different language
        if self._align_model is not None and self._current_language == language:
            return

        import whisperx

        logger.info("Loading WhisperX alignment model for language: %s", language)

        # Get language-specific model or use default
        if language in self.LANGUAGE_MODELS:
            logger.info("Using wav2vec2 model: %s", self.LANGUAGE_MODELS[language])
        else:
            logger.warning("No specific wav2vec2 model for %s, using default", language)

        try:
            self._align_model, self._metadata = whisperx.load_align_model(
                language_code=language,
                device=self.device,
            )
            self._current_language = language
            logger.info("WhisperX alignment model loaded successfully on %s", self.device)
        except Exception as e:
            logger.error("Failed to load alignment model: %s", e)
            raise

    def _load_diarize_pipeline(self):
        """Load speaker diarization pipeline (optional)."""
        if self._diarize_pipeline is not None:
            return

        try:
            import whisperx

            hf_token = getattr(settings, 'HUGGINGFACE_TOKEN', None)
            if not hf_token:
                logger.warning("HUGGINGFACE_TOKEN not set, diarization unavailable")
                return

            logger.info("Loading speaker diarization pipeline...")
            self._diarize_pipeline = whisperx.DiarizationPipeline(
                use_auth_token=hf_token,
                device=self.device
            )
            logger.info("Speaker diarization pipeline loaded")
        except Exception as e:
            logger.warning("Failed to load diarization pipeline: %s", e)

    async def align_transcription(
        self,
        audio_path: str,
        transcription: dict[str, Any],
        language: str | None = None,
        with_diarization: bool = False,
        progress_callback: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Align transcription with precise word-level timestamps.

        Args:
            audio_path: Path to audio file
            transcription: Transcription result from faster-whisper
            language: Language code (auto-detected if not specified)
            with_diarization: Include speaker diarization
            progress_callback: Progress callback function

        Returns:
            Aligned transcription with precise word timestamps
        """
        if not self.is_available():
            logger.warning("WhisperX not available, returning original transcription")
            return transcription

        # Run alignment in executor (WhisperX is synchronous)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._align_sync(
                audio_path,
                transcription,
                language,
                with_diarization,
                progress_callback
            )
        )

    def _align_sync(
        self,
        audio_path: str,
        transcription: dict[str, Any],
        language: str | None,
        with_diarization: bool,
        progress_callback: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Synchronous alignment implementation."""
        import whisperx

        if progress_callback:
            progress_callback(5)

        # Determine language
        lang = language or transcription.get("language", "fr")
        logger.info("Starting WhisperX alignment for %s (language: %s)", audio_path, lang)

        # Load audio
        if progress_callback:
            progress_callback(10)

        logger.debug("Loading audio for alignment...")
        audio = whisperx.load_audio(audio_path)

        if progress_callback:
            progress_callback(20)

        # Load alignment model
        self._load_align_model(lang)

        if progress_callback:
            progress_callback(30)

        # Convert transcription to WhisperX format if needed
        segments = self._convert_to_whisperx_format(transcription.get("segments", []))

        if not segments:
            logger.warning("No segments to align")
            return transcription

        if progress_callback:
            progress_callback(40)

        # Perform alignment
        logger.info("Performing forced alignment on %d segments...", len(segments))

        try:
            aligned_result = whisperx.align(
                segments,
                self._align_model,
                self._metadata,
                audio,
                self.device,
                return_char_alignments=False,  # We only need word-level
            )

            if progress_callback:
                progress_callback(70)

        except Exception as e:
            logger.error("WhisperX alignment failed: %s", e)
            logger.info("Returning original transcription with unmodified timestamps")
            return transcription

        # Optional: Speaker diarization
        if with_diarization:
            try:
                self._load_diarize_pipeline()
                if self._diarize_pipeline:
                    logger.info("Performing speaker diarization...")
                    diarize_segments = self._diarize_pipeline(audio)
                    aligned_result = whisperx.assign_word_speakers(
                        diarize_segments, aligned_result
                    )
                    if progress_callback:
                        progress_callback(85)
            except Exception as e:
                logger.warning("Diarization failed: %s", e)

        if progress_callback:
            progress_callback(90)

        # Convert back to our format
        result = self._convert_from_whisperx_format(
            aligned_result,
            original=transcription
        )

        if progress_callback:
            progress_callback(100)

        # Log improvement stats
        self._log_alignment_stats(transcription.get("segments", []), result.get("segments", []))

        return result

    def _convert_to_whisperx_format(self, segments: list[dict]) -> list[dict]:
        """Convert our segment format to WhisperX format."""
        whisperx_segments = []

        for seg in segments:
            whisperx_seg = {
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", ""),
            }

            # Include word-level if available (will be improved by alignment)
            if "words" in seg:
                whisperx_seg["words"] = [
                    {
                        "word": w.get("word", ""),
                        "start": w.get("start", 0),
                        "end": w.get("end", 0),
                    }
                    for w in seg["words"]
                ]

            whisperx_segments.append(whisperx_seg)

        return whisperx_segments

    def _convert_from_whisperx_format(
        self,
        aligned_result: dict,
        original: dict
    ) -> dict[str, Any]:
        """Convert WhisperX result back to our format."""
        aligned_segments = aligned_result.get("segments", [])

        result_segments = []
        for i, seg in enumerate(aligned_segments):
            seg_data = {
                "id": i,
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", "").strip(),
            }

            # Extract word-level timestamps
            if "words" in seg:
                seg_data["words"] = []
                for word in seg["words"]:
                    word_data = {
                        "word": word.get("word", ""),
                        "start": word.get("start", 0),
                        "end": word.get("end", 0),
                        "confidence": word.get("score", 0.95),  # WhisperX uses 'score'
                    }

                    # Include speaker if available
                    if "speaker" in word:
                        word_data["speaker"] = word["speaker"]

                    seg_data["words"].append(word_data)

            # Include speaker at segment level if available
            if "speaker" in seg:
                seg_data["speaker"] = seg["speaker"]

            result_segments.append(seg_data)

        return {
            "language": original.get("language", "fr"),
            "language_probability": original.get("language_probability", 1.0),
            "duration": original.get("duration", 0),
            "segments": result_segments,
            "text": original.get("text", ""),
            "aligned": True,  # Mark as aligned
            "alignment_method": "whisperx",
        }

    def _log_alignment_stats(self, original_segments: list, aligned_segments: list):
        """Log statistics about alignment improvements."""
        if not original_segments or not aligned_segments:
            return

        sum(
            len(seg.get("words", [])) for seg in original_segments
        )
        aligned_word_count = sum(
            len(seg.get("words", [])) for seg in aligned_segments
        )

        # Calculate average word duration improvement
        original_durations = []
        aligned_durations = []

        for seg in original_segments:
            for word in seg.get("words", []):
                dur = word.get("end", 0) - word.get("start", 0)
                if dur > 0:
                    original_durations.append(dur)

        for seg in aligned_segments:
            for word in seg.get("words", []):
                dur = word.get("end", 0) - word.get("start", 0)
                if dur > 0:
                    aligned_durations.append(dur)

        avg_original = sum(original_durations) / len(original_durations) if original_durations else 0
        avg_aligned = sum(aligned_durations) / len(aligned_durations) if aligned_durations else 0

        logger.info(
            "WhisperX alignment complete: %d segments, %d words. "
            "Avg word duration: %.3fs -> %.3fs",
            len(aligned_segments),
            aligned_word_count,
            avg_original,
            avg_aligned
        )


class WhisperXTranscriber:
    """Full WhisperX transcription + alignment pipeline.

    Alternative to faster-whisper that includes alignment in one pass.
    Use this when you want the most accurate timestamps possible.

    Note: Slower than faster-whisper's BatchedInferencePipeline but more accurate.
    """

    _instance: WhisperXTranscriber | None = None
    _model = None

    def __init__(self):
        self.device = "cuda" if WhisperXAligner._check_cuda() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.batch_size = 16 if self.device == "cuda" else 4

    @classmethod
    def get_instance(cls) -> WhisperXTranscriber:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        """Check if WhisperX transcription is available."""
        try:
            import whisperx
            return True
        except ImportError:
            return False

    def _load_model(self, model_name: str = "large-v3"):
        """Load WhisperX model."""
        if self._model is not None:
            return

        import whisperx

        logger.info("Loading WhisperX model: %s on %s (%s)",
                   model_name, self.device, self.compute_type)

        self._model = whisperx.load_model(
            model_name,
            self.device,
            compute_type=self.compute_type,
            asr_options={"word_timestamps": True}
        )

        logger.info("WhisperX model loaded successfully")

    async def transcribe_and_align(
        self,
        audio_path: str,
        language: str | None = None,
        model_name: str = "large-v3",
        with_diarization: bool = False,
        progress_callback: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Full transcription + alignment pipeline.

        Args:
            audio_path: Path to audio file
            language: Language code (auto-detected if not specified)
            model_name: Whisper model to use
            with_diarization: Include speaker diarization
            progress_callback: Progress callback

        Returns:
            Fully aligned transcription with precise word timestamps
        """
        if not self.is_available():
            raise RuntimeError("WhisperX not installed. Run: pip install whisperx")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._transcribe_and_align_sync(
                audio_path,
                language,
                model_name,
                with_diarization,
                progress_callback
            )
        )

    def _transcribe_and_align_sync(
        self,
        audio_path: str,
        language: str | None,
        model_name: str,
        with_diarization: bool,
        progress_callback: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Synchronous transcription + alignment."""
        import whisperx

        if progress_callback:
            progress_callback(5)

        logger.info("Starting WhisperX full pipeline for: %s", audio_path)

        # Load model
        self._load_model(model_name)

        if progress_callback:
            progress_callback(10)

        # Load audio
        audio = whisperx.load_audio(audio_path)

        if progress_callback:
            progress_callback(15)

        # Transcribe
        logger.info("Transcribing with WhisperX (batch_size=%d)...", self.batch_size)
        result = self._model.transcribe(
            audio,
            batch_size=self.batch_size,
            language=language,
        )

        detected_language = result.get("language", language or "fr")

        if progress_callback:
            progress_callback(50)

        # Load alignment model
        logger.info("Loading alignment model for language: %s", detected_language)
        align_model, metadata = whisperx.load_align_model(
            language_code=detected_language,
            device=self.device,
        )

        if progress_callback:
            progress_callback(60)

        # Align
        logger.info("Performing forced alignment...")
        aligned_result = whisperx.align(
            result["segments"],
            align_model,
            metadata,
            audio,
            self.device,
            return_char_alignments=False,
        )

        if progress_callback:
            progress_callback(80)

        # Optional diarization
        if with_diarization:
            try:
                hf_token = getattr(settings, 'HUGGINGFACE_TOKEN', None)
                if hf_token:
                    logger.info("Performing speaker diarization...")
                    diarize_model = whisperx.DiarizationPipeline(
                        use_auth_token=hf_token,
                        device=self.device
                    )
                    diarize_segments = diarize_model(audio)
                    aligned_result = whisperx.assign_word_speakers(
                        diarize_segments, aligned_result
                    )
            except Exception as e:
                logger.warning("Diarization failed: %s", e)

        if progress_callback:
            progress_callback(95)

        # Format result
        aligner = WhisperXAligner.get_instance()
        formatted = aligner._convert_from_whisperx_format(
            aligned_result,
            original={
                "language": detected_language,
                "language_probability": 1.0,
                "duration": len(audio) / 16000,  # WhisperX uses 16kHz
                "text": " ".join(s.get("text", "") for s in result.get("segments", [])),
            }
        )

        if progress_callback:
            progress_callback(100)

        logger.info("WhisperX pipeline complete: %d segments",
                   len(formatted.get("segments", [])))

        return formatted
