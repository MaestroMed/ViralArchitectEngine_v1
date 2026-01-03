"""Transcription service using faster-whisper."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from forge_engine.core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for audio transcription using faster-whisper."""
    
    _instance: Optional["TranscriptionService"] = None
    _model = None
    _model_name: Optional[str] = None
    
    def __init__(self):
        self.model_name = settings.WHISPER_MODEL
        self.device = settings.WHISPER_DEVICE
        self.compute_type = settings.WHISPER_COMPUTE_TYPE
    
    @classmethod
    def get_instance(cls) -> "TranscriptionService":
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
    
    def _load_model(self, model_name: Optional[str] = None):
        """Load the Whisper model."""
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
                logger.info("Attempting to load Whisper on %s (%s)...", device, compute_type)
                self._model = WhisperModel(
                    target_model,
                    device=device,
                    compute_type=compute_type,
                    cpu_threads=4,
                    num_workers=1
                )
                self._model_name = target_model
                logger.info("Whisper model loaded successfully on %s (%s)", device, compute_type)
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
                        num_workers=1
                    )
                    self._model_name = target_model
                    logger.info("Whisper model loaded on CPU (fallback)")
                else:
                    raise
    
    async def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
        initial_prompt: Optional[str] = None,
        custom_dictionary: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Transcribe audio file."""
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
                progress_callback
            )
        )
    
    def _transcribe_sync(
        self,
        audio_path: str,
        language: Optional[str],
        word_timestamps: bool,
        initial_prompt: Optional[str],
        custom_dictionary: Optional[List[str]],
        progress_callback: Optional[callable]
    ) -> Dict[str, Any]:
        """Synchronous transcription."""
        if progress_callback:
            progress_callback(0)
            
        logger.info("Loading model for transcription...")
        self._load_model()
        
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
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', audio_path],
                capture_output=True, text=True
            )
            audio_duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        except Exception:
            audio_duration = 0
        
        logger.info("Starting transcription of %s (duration: %.1fs)...", audio_path, audio_duration)
        
        if progress_callback:
            progress_callback(5)
        
        # Transcribe - VAD filter disabled for faster processing on long videos
        # VAD pre-analysis can take a very long time on 2h+ videos
        use_vad = audio_duration < 3600  # Only use VAD for videos < 1h
        logger.info("VAD filter: %s (duration: %.0fs)", "enabled" if use_vad else "disabled (long video)", audio_duration)
        
        segments, info = self._model.transcribe(
            audio_path,
            language=language,
            word_timestamps=word_timestamps,
            initial_prompt=prompt if prompt else None,
            vad_filter=use_vad,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200
            ) if use_vad else None,
            condition_on_previous_text=True,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6
        )
        
        logger.info("Transcription generator started, processing segments...")
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
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
        segments: List[Dict[str, Any]],
        window_size: int = 5
    ) -> List[str]:
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


