"""Audio analysis service."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

# Optional numpy import
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

logger = logging.getLogger(__name__)


class AudioAnalyzer:
    """Service for analyzing audio characteristics."""
    
    def __init__(self):
        self.sample_rate = 16000
    
    async def analyze(
        self,
        audio_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Analyze audio file for energy, peaks, and patterns."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._analyze_sync(audio_path, progress_callback)
        )
    
    def _analyze_sync(
        self,
        audio_path: str,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """Synchronous audio analysis."""
        if not HAS_NUMPY:
            logger.warning("numpy not available, returning minimal analysis")
            return {
                "energy_timeline": [],
                "peaks": [],
                "silences": [],
                "speech_rate": [],
            }
        
        try:
            import librosa
        except ImportError:
            logger.warning("librosa not available, returning minimal analysis")
            return {
                "energy_timeline": [],
                "peaks": [],
                "silences": [],
                "speech_rate": [],
            }
        
        # Load audio
        if progress_callback:
            progress_callback(10)
        
        y, sr = librosa.load(audio_path, sr=self.sample_rate)
        duration = len(y) / sr
        
        if progress_callback:
            progress_callback(30)
        
        # Calculate RMS energy
        hop_length = int(sr * 0.5)  # 0.5 second resolution
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        
        # Normalize RMS
        rms_normalized = rms / (rms.max() + 1e-8)
        
        # Create energy timeline
        energy_timeline = []
        for i, energy in enumerate(rms_normalized):
            time = i * hop_length / sr
            energy_timeline.append({
                "time": float(time),
                "value": float(energy)
            })
        
        if progress_callback:
            progress_callback(50)
        
        # Detect peaks (high energy moments)
        peak_indices = np.where(rms_normalized > 0.7)[0]
        peaks = [
            {"time": float(i * hop_length / sr), "value": float(rms_normalized[i])}
            for i in peak_indices
        ]
        
        if progress_callback:
            progress_callback(70)
        
        # Detect silences
        silence_threshold = 0.05
        silence_indices = np.where(rms_normalized < silence_threshold)[0]
        
        silences = []
        if len(silence_indices) > 0:
            # Group consecutive silence frames
            silence_groups = np.split(silence_indices, np.where(np.diff(silence_indices) != 1)[0] + 1)
            for group in silence_groups:
                if len(group) >= 2:  # At least 1 second of silence
                    start_time = group[0] * hop_length / sr
                    end_time = group[-1] * hop_length / sr
                    silences.append({
                        "start": float(start_time),
                        "end": float(end_time)
                    })
        
        if progress_callback:
            progress_callback(90)
        
        # Detect laughter-like patterns (high frequency bursts)
        laughter_patterns = self._detect_laughter_patterns(y, sr)
        
        if progress_callback:
            progress_callback(100)
        
        return {
            "duration": float(duration),
            "energy_timeline": energy_timeline,
            "peaks": peaks,
            "silences": silences,
            "laughter_patterns": laughter_patterns,
            "average_energy": float(np.mean(rms_normalized)),
            "energy_variance": float(np.var(rms_normalized)),
        }
    
    def _detect_laughter_patterns(
        self,
        y: np.ndarray,
        sr: int
    ) -> List[Dict[str, Any]]:
        """Detect laughter-like audio patterns (heuristic)."""
        try:
            import librosa
        except ImportError:
            return []
        
        patterns = []
        
        # Calculate spectral features
        hop_length = int(sr * 0.1)  # 100ms resolution
        
        # Spectral centroid (laughter tends to have higher centroid)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
        
        # Spectral flux (laughter has high variability)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        
        # Look for bursts of high centroid + high onset strength
        threshold_centroid = np.percentile(centroid, 80)
        threshold_onset = np.percentile(onset_env, 80)
        
        high_activity = (centroid > threshold_centroid) & (onset_env > threshold_onset)
        
        # Find continuous regions
        indices = np.where(high_activity)[0]
        if len(indices) > 0:
            groups = np.split(indices, np.where(np.diff(indices) > 5)[0] + 1)
            for group in groups:
                if len(group) >= 3:  # At least 300ms
                    time = float(group[0] * hop_length / sr)
                    confidence = float(np.mean(onset_env[group]) / (onset_env.max() + 1e-8))
                    patterns.append({
                        "time": time,
                        "confidence": confidence
                    })
        
        return patterns

