"""Transcription service using faster-whisper with batched inference.

Features:
- Auto-detection of optimal batch_size based on GPU VRAM
- Multi-GPU support via GPUManager
- BatchedInferencePipeline for 4-6x speedup
- INT8 quantization for modern GPUs
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Optional

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


def auto_detect_batch_size(vram_gb: float) -> int:
    """Automatically detect optimal batch_size based on VRAM.

    Batch size recommendations based on testing:
    - 32GB (RTX 5090): batch_size=48-64
    - 24GB (RTX 4090): batch_size=32
    - 16GB (RTX 5080): batch_size=24
    - 12GB (RTX 4070 Ti): batch_size=16
    - 8GB (RTX 3070): batch_size=8
    - 6GB or less: batch_size=4

    Formula: ~2.5 batch per GB, capped by model size requirements.
    """
    if vram_gb >= 30:
        return 64  # RTX 5090 (32GB)
    elif vram_gb >= 22:
        return 32  # RTX 4090 (24GB)
    elif vram_gb >= 14:
        return 24  # RTX 5080 (16GB)
    elif vram_gb >= 10:
        return 16  # RTX 4070 Ti (12GB)
    elif vram_gb >= 7:
        return 8   # RTX 3070 (8GB)
    else:
        return 4   # Low VRAM


def auto_detect_num_workers(vram_gb: float) -> int:
    """Automatically detect optimal num_workers based on VRAM.

    More workers = better GPU utilization but more VRAM usage.
    """
    if vram_gb >= 24:
        return 4
    elif vram_gb >= 12:
        return 2
    else:
        return 1


class TranscriptionService:
    """Service for audio transcription using faster-whisper with batched inference.

    Uses BatchedInferencePipeline for 4-6x speedup on GPU.
    """

    _instance: TranscriptionService | None = None
    _model = None
    _batched_model = None  # BatchedInferencePipeline for turbo mode
    _model_name: str | None = None

    def __init__(self):
        self.model_name = settings.WHISPER_MODEL
        self.device = settings.WHISPER_DEVICE
        self.compute_type = settings.WHISPER_COMPUTE_TYPE

        # Auto-detect batch size based on VRAM
        self._detected_vram_gb: float | None = None
        self._auto_batch_size: int | None = None
        self._auto_num_workers: int | None = None

        # Will be auto-detected on first use, or use configured value as fallback
        self.batch_size = getattr(settings, 'WHISPER_BATCH_SIZE', 16)

        # Try to auto-detect GPU and optimize settings
        self._auto_detect_gpu_settings()

    @classmethod
    def get_instance(cls) -> TranscriptionService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_available(self) -> bool:
        """Check if faster-whisper is available."""
        try:
            from faster_whisper import WhisperModel
            return True
        except ImportError:
            return False

    def _auto_detect_gpu_settings(self):
        """Auto-detect GPU and optimize batch_size/num_workers."""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Get first GPU's VRAM in GB
                vram_mb = float(result.stdout.strip().split('\n')[0])
                self._detected_vram_gb = vram_mb / 1024

                # Auto-detect optimal settings
                self._auto_batch_size = auto_detect_batch_size(self._detected_vram_gb)
                self._auto_num_workers = auto_detect_num_workers(self._detected_vram_gb)

                # Update batch_size if auto-detected is better than default
                if self._auto_batch_size != self.batch_size:
                    logger.info(
                        "Auto-detected GPU: %.1f GB VRAM -> batch_size=%d, num_workers=%d",
                        self._detected_vram_gb, self._auto_batch_size, self._auto_num_workers
                    )
                    self.batch_size = self._auto_batch_size
        except Exception as e:
            logger.debug("GPU auto-detection failed (will use defaults): %s", e)

    @property
    def detected_vram_gb(self) -> float | None:
        """Get detected GPU VRAM in GB."""
        return self._detected_vram_gb

    @property
    def optimal_batch_size(self) -> int:
        """Get optimal batch size for current GPU."""
        return self._auto_batch_size or self.batch_size

    @property
    def optimal_num_workers(self) -> int:
        """Get optimal num_workers for current GPU."""
        return self._auto_num_workers or getattr(settings, 'WHISPER_NUM_WORKERS', 2)

    @staticmethod
    def get_available_models() -> list[dict[str, Any]]:
        """Get list of available Whisper models with metadata."""
        return [
            {
                "id": "large-v3",
                "name": "Large V3",
                "description": "Meilleure qualité, plus lent",
                "speed": 1.0,
                "quality": 100,
                "vram_gb": 10,
            },
            {
                "id": "distil-large-v3",
                "name": "Distil Large V3 (TURBO)",
                "description": "5.8x plus rapide, qualité proche",
                "speed": 5.8,
                "quality": 97,
                "vram_gb": 6,
            },
            {
                "id": "medium",
                "name": "Medium",
                "description": "Équilibre vitesse/qualité",
                "speed": 3.0,
                "quality": 90,
                "vram_gb": 5,
            },
            {
                "id": "small",
                "name": "Small",
                "description": "Rapide, qualité acceptable",
                "speed": 6.0,
                "quality": 80,
                "vram_gb": 2,
            },
            {
                "id": "base",
                "name": "Base",
                "description": "Très rapide, qualité réduite",
                "speed": 10.0,
                "quality": 70,
                "vram_gb": 1,
            },
        ]

    def _load_model(self, model_name: str | None = None):
        """Load the Whisper model with BatchedInferencePipeline for turbo mode."""
        if not self.is_available():
            raise RuntimeError("faster-whisper is not installed")

        from faster_whisper import WhisperModel

        target_model = model_name or self.model_name

        if self._model is None or self._model_name != target_model:
            logger.info("Loading Whisper model: %s", target_model)

            # Determine device using ctranslate2
            device = self.device
            compute_type = self.compute_type

            if device == "auto":
                # Use ctranslate2 directly for CUDA detection (what faster-whisper uses)
                try:
                    import ctranslate2
                    cuda_count = ctranslate2.get_cuda_device_count()
                    if cuda_count > 0:
                        device = "cuda"
                        # Get GPU name via nvidia-smi
                        try:
                            import subprocess
                            result = subprocess.run(
                                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                                capture_output=True, text=True, timeout=5
                            )
                            if result.returncode == 0:
                                gpu_info = result.stdout.strip().split(',')
                                gpu_name = gpu_info[0].strip() if gpu_info else "NVIDIA GPU"
                                gpu_memory = float(gpu_info[1].strip()) / 1024 if len(gpu_info) > 1 else 0
                                logger.info("CUDA available via ctranslate2: %s (%.1f GB VRAM)", gpu_name, gpu_memory)
                            else:
                                logger.info("CUDA available via ctranslate2: %d device(s)", cuda_count)
                        except Exception:
                            logger.info("CUDA available via ctranslate2: %d device(s)", cuda_count)
                    else:
                        device = "cpu"
                        logger.info("No CUDA devices found, using CPU")
                except ImportError:
                    logger.warning("ctranslate2 not installed, falling back to CPU")
                    device = "cpu"
                except Exception as e:
                    logger.warning("CUDA detection failed: %s, using CPU", e)
                    device = "cpu"

            if device == "cpu":
                compute_type = "float32"

            # Try loading model with fallback
            try:
                # Use auto-detected or configured num_workers
                num_workers = self.optimal_num_workers
                batch_size = self.optimal_batch_size

                logger.info(
                    "Loading Whisper on %s (%s, workers=%d, batch_size=%d, vram=%.1fGB)...",
                    device, compute_type, num_workers, batch_size,
                    self._detected_vram_gb or 0
                )
                self._model = WhisperModel(
                    target_model,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=4,
                    num_workers=num_workers
                )
                self._model_name = target_model
                logger.info("Whisper model loaded successfully on %s (%s)", device, compute_type)

                # Create BatchedInferencePipeline for turbo mode (4-6x speedup on GPU)
                if device == "cuda":
                    try:
                        from faster_whisper import BatchedInferencePipeline
                        self._batched_model = BatchedInferencePipeline(model=self._model)
                        logger.info("BatchedInferencePipeline created (TURBO MODE enabled, batch_size=%d)", self.batch_size)
                    except ImportError:
                        logger.warning("BatchedInferencePipeline not available, using standard mode")
                        self._batched_model = None
                    except Exception as e:
                        logger.warning("Failed to create BatchedInferencePipeline: %s", e)
                        self._batched_model = None
                else:
                    self._batched_model = None

            except Exception as e:
                if device == "cuda":
                    logger.warning("CUDA loading failed (%s), falling back to CPU", e)
                    device = "cpu"
                    compute_type = "float32"
                    self._model = WhisperModel(
                        target_model,
                        device=device,
                        compute_type=compute_type,
                        cpu_threads=4,
                        num_workers=1  # Use 1 for CPU fallback
                    )
                    self._model_name = target_model
                    self._batched_model = None
                    logger.info("Whisper model loaded on CPU (fallback, workers=1)")
                else:
                    raise

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        word_timestamps: bool = True,
        initial_prompt: str | None = None,
        custom_dictionary: list[str] | None = None,
        progress_callback: Callable[..., Any] | None = None,
        model_override: str | None = None,  # Use different model (e.g. "distil-large-v3" for preview)
        turbo_mode: bool | None = None,  # Override turbo mode setting
    ) -> dict[str, Any]:
        """Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Language code (default: settings.WHISPER_LANGUAGE)
            word_timestamps: Include word-level timestamps
            initial_prompt: Initial prompt for context
            custom_dictionary: Custom words for better recognition
            progress_callback: Progress callback function
            model_override: Override model (e.g. "distil-large-v3" for preview mode)
            turbo_mode: Override turbo mode (batched inference)
        """
        import asyncio

        # Run in executor since faster-whisper is synchronous
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._transcribe_sync(
                audio_path,
                language,
                word_timestamps,
                initial_prompt,
                custom_dictionary,
                progress_callback,
                model_override,
                turbo_mode
            )
        )

    def _transcribe_sync(
        self,
        audio_path: str,
        language: str | None,
        word_timestamps: bool,
        initial_prompt: str | None,
        custom_dictionary: list[str] | None,
        progress_callback: Callable[..., Any] | None,
        model_override: str | None = None,
        turbo_mode: bool | None = None
    ) -> dict[str, Any]:
        """Synchronous transcription with optional model override.

        Supports preview mode with distil-large-v3 for rapid transcription.
        """
        if progress_callback:
            progress_callback(0)

        # Use configured default language if not specified
        if language is None:
            language = settings.WHISPER_LANGUAGE
            logger.info("Using default language from config: %s", language)
        else:
            logger.info("Using specified language: %s", language)

        # Handle model override (e.g. for preview mode with distil-large-v3)
        target_model = model_override or self.model_name
        if model_override and model_override != self.model_name:
            logger.info("Using model override: %s (instead of %s)", model_override, self.model_name)
            # Force reload if different model requested
            if self._model_name != model_override:
                self._model = None
                self._batched_model = None

        logger.info("Loading model for transcription: %s", target_model)
        self._load_model(target_model)

        if progress_callback:
            progress_callback(2)

        # Build initial prompt with custom dictionary
        prompt = initial_prompt or ""
        if custom_dictionary:
            # Limite les mots du dictionnaire à 200 pour éviter un prompt trop long
            dict_words = custom_dictionary[:200]
            prompt = ", ".join(dict_words) + ". " + prompt
            logger.info("Using custom dictionary with %d words", len(dict_words))

        # Get audio duration for progress estimation
        try:
            import subprocess

            from forge_engine.core.config import settings as _s
            _ffprobe = getattr(_s, "FFPROBE_PATH", "ffprobe")
            result = subprocess.run(
                [_ffprobe, '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', audio_path],
                capture_output=True, text=True, timeout=10
            )
            audio_duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        except Exception:
            audio_duration = 0

        logger.info("Starting transcription of %s (duration: %.1fs)...", audio_path, audio_duration)

        if progress_callback:
            progress_callback(5)

        # ========================================
        # TURBO MODE: Use BatchedInferencePipeline for 4-6x speedup
        # ========================================
        # Determine if we should use turbo mode
        turbo_enabled = turbo_mode if turbo_mode is not None else getattr(settings, 'WHISPER_TURBO_MODE', True)
        use_batched = self._batched_model is not None and turbo_enabled

        # VAD parameters optimized for streaming content
        vad_params = {
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "min_silence_duration_ms": 800,  # Slightly aggressive for streams
            "speech_pad_ms": 150
        }

        if use_batched:
            # TURBO MODE: Batched inference (4-6x faster on GPU)
            logger.info("TURBO MODE: Using BatchedInferencePipeline (batch_size=%d)", self.batch_size)

            segments, info = self._batched_model.transcribe(
                audio_path,
                language=language,
                word_timestamps=word_timestamps,
                initial_prompt=prompt if prompt else None,
                batch_size=self.batch_size,
                vad_filter=True,  # Always use VAD with batched mode
                vad_parameters=vad_params,
            )
        else:
            # Standard mode (fallback)
            use_vad = audio_duration < 3600  # Only use VAD for videos < 1h in standard mode
            logger.info("Standard mode: VAD=%s (duration: %.0fs)", use_vad, audio_duration)

            segments, info = self._model.transcribe(
                audio_path,
                language=language,
                word_timestamps=word_timestamps,
                initial_prompt=prompt if prompt else None,
                vad_filter=use_vad,
                vad_parameters=vad_params if use_vad else None,
                condition_on_previous_text=True,
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6
            )

        logger.info("Transcription %s started, processing segments...", "TURBO" if use_batched else "standard")
        if progress_callback:
            progress_callback(7)

        # Process segments - iterate on generator for real-time progress
        result_segments = []
        full_text_parts = []
        segment_count = 0
        last_end = 0
        last_progress_log = 0

        for segment in segments:
            seg_data = {
                "id": segment_count,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }

            if word_timestamps and segment.words:
                seg_data["words"] = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.probability
                    }
                    for word in segment.words
                ]

            result_segments.append(seg_data)
            full_text_parts.append(segment.text.strip())
            segment_count += 1
            last_end = segment.end

            # Update progress based on audio position
            if audio_duration > 0:
                pct = min(95, 7 + (last_end / audio_duration) * 88)
                if progress_callback:
                    progress_callback(pct)
                # Log every 5% progress
                if int(pct) >= last_progress_log + 5:
                    logger.info("Transcription: %.0f%% (segment %d, %.1fs/%.1fs)", pct, segment_count, last_end, audio_duration)
                    last_progress_log = int(pct)
            elif segment_count % 20 == 0:
                logger.info("Transcribed %d segments (%.1fs)...", segment_count, last_end)

        if progress_callback:
            progress_callback(100)

        logger.info("Transcription complete: %d segments, %.1fs duration", segment_count, info.duration)

        return {
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
            "segments": result_segments,
            "text": " ".join(full_text_parts),
        }

    def detect_hooks_and_punchlines(
        self,
        segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect potential hooks and punchlines in transcript."""
        # Hook patterns (French + English)
        hook_patterns = [
            # Interrogatives
            r"\?",
            # Exclamations
            r"!",
            # French intensifiers
            r"\b(non mais|attends?|regarde[zs]?|wesh|j'?te jure|putain|bordel|incroyable|dingue|ouf)\b",
            # English intensifiers
            r"\b(wait|look|holy|insane|crazy|unbelievable|no way|what the)\b",
            # Setup patterns
            r"\b(alors|donc|en fait|tu sais|vous savez|basically|so basically|let me tell you)\b",
        ]

        import re

        enhanced_segments = []
        for seg in segments:
            text = seg.get("text", "").lower()

            hook_score = 0
            hook_reasons = []

            for pattern in hook_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    hook_score += 1
                    hook_reasons.append(f"Pattern: {pattern}")

            # Check for question structure
            if text.strip().endswith("?"):
                hook_score += 2
                hook_reasons.append("Question")

            # Check for short punchy sentences
            words = text.split()
            if 3 <= len(words) <= 10:
                hook_score += 1
                hook_reasons.append("Short punchy")

            enhanced_segments.append({
                **seg,
                "hook_score": hook_score,
                "hook_reasons": hook_reasons,
                "is_potential_hook": hook_score >= 2,
            })

        return enhanced_segments

    def generate_topic_labels(
        self,
        segments: list[dict[str, Any]],
        window_size: int = 5
    ) -> list[str]:
        """Generate topic labels for groups of segments."""
        labels = []

        for i in range(0, len(segments), window_size):
            window = segments[i:i + window_size]
            combined_text = " ".join(s.get("text", "") for s in window)

            # Simple heuristic: use first meaningful sentence
            sentences = combined_text.split(".")
            if sentences:
                label = sentences[0].strip()[:50]
                if len(sentences[0]) > 50:
                    label += "..."
            else:
                label = f"Segment {i // window_size + 1}"

            labels.append(label)

        return labels


