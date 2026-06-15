"""Advanced Audio Analysis Service with Event Detection."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Optional

# Optional numpy import
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

# Check for torchaudio
try:
    import torch
    import torchaudio
    HAS_TORCHAUDIO = True
except ImportError:
    HAS_TORCHAUDIO = False

logger = logging.getLogger(__name__)


class AudioEventType(StrEnum):
    """Types of audio events that can be detected."""
    LAUGHTER = "laughter"
    CHEER = "cheer"
    APPLAUSE = "applause"
    SCREAM = "scream"
    GASP = "gasp"
    MUSIC = "music"
    SPEECH_EXCITEMENT = "speech_excitement"
    GAME_EXPLOSION = "game_explosion"
    GAME_GUNSHOT = "game_gunshot"
    GAME_ACHIEVEMENT = "game_achievement"
    SILENCE = "silence"


@dataclass
class AudioEvent:
    """Represents a detected audio event."""
    event_type: AudioEventType
    start_time: float
    end_time: float
    confidence: float
    viral_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioAnalysisResult:
    """Complete audio analysis result."""
    duration: float
    energy_timeline: list[dict[str, Any]]
    peaks: list[dict[str, Any]]
    silences: list[dict[str, Any]]
    events: list[AudioEvent]
    average_energy: float
    energy_variance: float
    speech_rate_estimate: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)


class AudioAnalyzer:
    """Advanced service for analyzing audio characteristics and detecting events."""

    # Viral potential scores for different events
    EVENT_VIRAL_SCORES = {
        AudioEventType.LAUGHTER: 0.95,
        AudioEventType.CHEER: 0.9,
        AudioEventType.APPLAUSE: 0.85,
        AudioEventType.SCREAM: 0.8,
        AudioEventType.GASP: 0.85,
        AudioEventType.SPEECH_EXCITEMENT: 0.75,
        AudioEventType.GAME_EXPLOSION: 0.7,
        AudioEventType.GAME_GUNSHOT: 0.5,
        AudioEventType.GAME_ACHIEVEMENT: 0.8,
        AudioEventType.MUSIC: 0.3,
        AudioEventType.SILENCE: 0.0,
    }

    _instance: Optional["AudioAnalyzer"] = None

    def __init__(self):
        self.sample_rate = 16000
        self._classifier = None
        self._classifier_available = None

    @classmethod
    def get_instance(cls) -> "AudioAnalyzer":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_advanced_available(self) -> bool:
        """Check if advanced audio event detection is available."""
        return HAS_TORCHAUDIO and HAS_NUMPY

    async def analyze(
        self,
        audio_path: str,
        progress_callback: Callable[[float], None] | None = None
    ) -> dict[str, Any]:
        """Analyze audio file for energy, peaks, and patterns."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._analyze_sync(audio_path, progress_callback)
        )

    def _analyze_sync(
        self,
        audio_path: str,
        progress_callback: Callable[[float], None] | None = None
    ) -> dict[str, Any]:
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

        # (Laughter is detected as part of _detect_audio_events below via
        # _detect_laughter; a stray call to a non-existent
        # _detect_laughter_patterns used to crash audio analysis here.)

        if progress_callback:
            progress_callback(100)

        # Detect audio events
        events = self._detect_audio_events(y, sr, rms_normalized, hop_length)

        # Calculate speech rate estimate from onset detection
        speech_rate = self._estimate_speech_rate(y, sr)

        # Generate summary
        summary = self._generate_summary(events, duration, np.mean(rms_normalized))

        return AudioAnalysisResult(
            duration=float(duration),
            energy_timeline=energy_timeline,
            peaks=peaks,
            silences=silences,
            events=events,
            average_energy=float(np.mean(rms_normalized)),
            energy_variance=float(np.var(rms_normalized)),
            speech_rate_estimate=speech_rate,
            summary=summary
        )

    def _detect_audio_events(
        self,
        y: "np.ndarray",
        sr: int,
        rms_normalized: "np.ndarray",
        rms_hop_length: int
    ) -> list[AudioEvent]:
        """Detect various audio events in the signal."""
        events: list[AudioEvent] = []

        try:
            import librosa
        except ImportError:
            return events

        # 1. Detect laughter patterns
        laughter_events = self._detect_laughter(y, sr)
        events.extend(laughter_events)

        # 2. Detect cheering/applause
        cheer_events = self._detect_cheering(y, sr)
        events.extend(cheer_events)

        # 3. Detect screams/gasps (high energy, high frequency transients)
        scream_events = self._detect_screams(y, sr)
        events.extend(scream_events)

        # 4. Detect speech excitement (rapid speech, high pitch variation)
        excitement_events = self._detect_speech_excitement(y, sr)
        events.extend(excitement_events)

        # 5. Detect game sounds (explosions, gunshots)
        game_events = self._detect_game_sounds(y, sr)
        events.extend(game_events)

        # Sort by time
        events.sort(key=lambda e: e.start_time)

        return events

    def _detect_laughter(
        self,
        y: "np.ndarray",
        sr: int
    ) -> list[AudioEvent]:
        """Detect laughter patterns using spectral analysis."""
        import librosa

        events = []
        hop_length = int(sr * 0.1)  # 100ms resolution

        # Spectral centroid (laughter tends to have higher centroid)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]

        # Zero crossing rate (laughter has high ZCR variability)
        zcr = librosa.feature.zero_crossing_rate(y=y, hop_length=hop_length)[0]

        # Onset strength (laughter has rhythmic bursts)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

        # Laughter detection: high centroid + high ZCR + rhythmic onsets
        threshold_centroid = np.percentile(centroid, 75)
        threshold_zcr = np.percentile(zcr, 70)
        threshold_onset = np.percentile(onset_env, 70)

        high_activity = (
            (centroid > threshold_centroid) &
            (zcr > threshold_zcr) &
            (onset_env > threshold_onset)
        )

        # Find continuous regions
        indices = np.where(high_activity)[0]
        if len(indices) > 0:
            groups = np.split(indices, np.where(np.diff(indices) > 3)[0] + 1)
            for group in groups:
                if len(group) >= 3:  # At least 300ms
                    start_time = float(group[0] * hop_length / sr)
                    end_time = float(group[-1] * hop_length / sr)
                    confidence = float(np.mean(onset_env[group]) / (onset_env.max() + 1e-8))

                    if confidence > 0.3:
                        events.append(AudioEvent(
                            event_type=AudioEventType.LAUGHTER,
                            start_time=start_time,
                            end_time=end_time,
                            confidence=confidence,
                            viral_score=self.EVENT_VIRAL_SCORES[AudioEventType.LAUGHTER] * confidence
                        ))

        return events

    def _detect_cheering(
        self,
        y: "np.ndarray",
        sr: int
    ) -> list[AudioEvent]:
        """Detect cheering/applause patterns."""
        import librosa

        events = []
        hop_length = int(sr * 0.2)  # 200ms resolution

        # RMS energy
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

        # Spectral bandwidth (cheering is broadband)
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length)[0]

        # Spectral flatness (cheering is noise-like, high flatness)
        flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length)[0]

        # Cheering: high energy + high bandwidth + high flatness (noise-like)
        threshold_rms = np.percentile(rms, 70)
        threshold_bandwidth = np.percentile(bandwidth, 70)
        threshold_flatness = np.percentile(flatness, 60)

        cheering = (
            (rms > threshold_rms) &
            (bandwidth > threshold_bandwidth) &
            (flatness > threshold_flatness)
        )

        indices = np.where(cheering)[0]
        if len(indices) > 0:
            groups = np.split(indices, np.where(np.diff(indices) > 3)[0] + 1)
            for group in groups:
                if len(group) >= 5:  # At least 1 second
                    start_time = float(group[0] * hop_length / sr)
                    end_time = float(group[-1] * hop_length / sr)
                    confidence = float(np.mean(flatness[group]))

                    if confidence > 0.2:
                        # Distinguish between cheer and applause
                        avg_flatness = np.mean(flatness[group])
                        event_type = AudioEventType.APPLAUSE if avg_flatness > 0.5 else AudioEventType.CHEER

                        events.append(AudioEvent(
                            event_type=event_type,
                            start_time=start_time,
                            end_time=end_time,
                            confidence=confidence,
                            viral_score=self.EVENT_VIRAL_SCORES[event_type] * confidence
                        ))

        return events

    def _detect_screams(
        self,
        y: "np.ndarray",
        sr: int
    ) -> list[AudioEvent]:
        """Detect screams and gasps (sudden high energy, high frequency)."""
        import librosa

        events = []
        hop_length = int(sr * 0.05)  # 50ms resolution for transients

        # Onset strength for sudden changes
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

        # Spectral centroid (screams have high frequency content)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]

        # RMS for energy
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

        # Screams: sudden onset + high centroid + high energy
        threshold_onset = np.percentile(onset_env, 90)
        threshold_centroid = np.percentile(centroid, 85)
        threshold_rms = np.percentile(rms, 80)

        scream_candidates = (
            (onset_env > threshold_onset) &
            (centroid > threshold_centroid) &
            (rms > threshold_rms)
        )

        indices = np.where(scream_candidates)[0]
        if len(indices) > 0:
            groups = np.split(indices, np.where(np.diff(indices) > 5)[0] + 1)
            for group in groups:
                if len(group) >= 2:  # At least 100ms
                    start_time = float(group[0] * hop_length / sr)
                    end_time = float(group[-1] * hop_length / sr)
                    confidence = float(np.mean(onset_env[group]) / (onset_env.max() + 1e-8))

                    # Short = gasp, long = scream
                    duration = end_time - start_time
                    event_type = AudioEventType.GASP if duration < 0.5 else AudioEventType.SCREAM

                    if confidence > 0.4:
                        events.append(AudioEvent(
                            event_type=event_type,
                            start_time=start_time,
                            end_time=end_time,
                            confidence=confidence,
                            viral_score=self.EVENT_VIRAL_SCORES[event_type] * confidence
                        ))

        return events

    def _detect_speech_excitement(
        self,
        y: "np.ndarray",
        sr: int
    ) -> list[AudioEvent]:
        """Detect excited speech patterns (high pitch variation, fast rate)."""
        import librosa

        events = []
        hop_length = int(sr * 0.1)  # 100ms

        # Pitch tracking (excited speech has higher pitch)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr, hop_length=hop_length)

        # Get dominant pitch per frame
        pitch_values = []
        for i in range(pitches.shape[1]):
            index = magnitudes[:, i].argmax()
            pitch = pitches[index, i]
            pitch_values.append(pitch if pitch > 0 else 0)

        pitch_values = np.array(pitch_values)

        # RMS energy
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

        # Onset rate (excited speech is faster)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

        # Detect high pitch + high energy + high onset
        # Filter out zero pitches
        valid_pitch = pitch_values > 0
        if np.sum(valid_pitch) > 0:
            avg_pitch = np.mean(pitch_values[valid_pitch])

            threshold_pitch = avg_pitch * 1.3  # 30% above average
            threshold_rms = np.percentile(rms, 70)
            threshold_onset = np.percentile(onset_env, 70)

            excitement = (
                valid_pitch &
                (pitch_values > threshold_pitch) &
                (rms > threshold_rms) &
                (onset_env > threshold_onset)
            )

            indices = np.where(excitement)[0]
            if len(indices) > 0:
                groups = np.split(indices, np.where(np.diff(indices) > 5)[0] + 1)
                for group in groups:
                    if len(group) >= 5:  # At least 500ms
                        start_time = float(group[0] * hop_length / sr)
                        end_time = float(group[-1] * hop_length / sr)
                        confidence = min(1.0, (np.mean(pitch_values[group]) - avg_pitch) / (avg_pitch + 1e-8))

                        if confidence > 0.2:
                            events.append(AudioEvent(
                                event_type=AudioEventType.SPEECH_EXCITEMENT,
                                start_time=start_time,
                                end_time=end_time,
                                confidence=confidence,
                                viral_score=self.EVENT_VIRAL_SCORES[AudioEventType.SPEECH_EXCITEMENT] * confidence
                            ))

        return events

    def _detect_game_sounds(
        self,
        y: "np.ndarray",
        sr: int
    ) -> list[AudioEvent]:
        """Detect game-related sounds (explosions, gunshots)."""
        import librosa

        events = []
        hop_length = int(sr * 0.02)  # 20ms for fast transients

        # Onset envelope
        onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)

        # Spectral features
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
        librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop_length)[0]

        # Explosions: sudden loud low-frequency bursts
        threshold_onset = np.percentile(onset_env, 95)
        threshold_centroid_low = np.percentile(centroid, 30)  # Lower centroid

        explosion_candidates = (
            (onset_env > threshold_onset) &
            (centroid < threshold_centroid_low)
        )

        indices = np.where(explosion_candidates)[0]
        if len(indices) > 0:
            groups = np.split(indices, np.where(np.diff(indices) > 10)[0] + 1)
            for group in groups:
                if len(group) >= 1:
                    start_time = float(group[0] * hop_length / sr)
                    end_time = float(min(group[-1] * hop_length / sr + 0.3, len(y) / sr))
                    confidence = float(np.mean(onset_env[group]) / (onset_env.max() + 1e-8))

                    if confidence > 0.5:
                        events.append(AudioEvent(
                            event_type=AudioEventType.GAME_EXPLOSION,
                            start_time=start_time,
                            end_time=end_time,
                            confidence=confidence,
                            viral_score=self.EVENT_VIRAL_SCORES[AudioEventType.GAME_EXPLOSION] * confidence
                        ))

        # Gunshots: very short, sharp transients
        threshold_onset_gunshot = np.percentile(onset_env, 98)

        gunshot_candidates = onset_env > threshold_onset_gunshot
        indices = np.where(gunshot_candidates)[0]

        for idx in indices:
            time = float(idx * hop_length / sr)
            confidence = float(onset_env[idx] / (onset_env.max() + 1e-8))

            if confidence > 0.6:
                events.append(AudioEvent(
                    event_type=AudioEventType.GAME_GUNSHOT,
                    start_time=time,
                    end_time=time + 0.1,
                    confidence=confidence,
                    viral_score=self.EVENT_VIRAL_SCORES[AudioEventType.GAME_GUNSHOT] * confidence
                ))

        return events

    def _estimate_speech_rate(
        self,
        y: "np.ndarray",
        sr: int
    ) -> float:
        """Estimate speech rate in syllables per second."""
        try:
            import librosa

            # Onset detection as proxy for syllable rate
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)

            duration = len(y) / sr
            if duration > 0:
                return len(onsets) / duration
            return 0.0
        except:
            return 0.0

    def _generate_summary(
        self,
        events: list[AudioEvent],
        duration: float,
        avg_energy: float
    ) -> dict[str, Any]:
        """Generate audio analysis summary."""
        # Count events by type
        event_counts = {}
        for event in events:
            event_type = event.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        # Calculate total viral score
        total_viral_score = sum(e.viral_score for e in events) / max(len(events), 1)

        # Find peak moments (highest viral score events)
        sorted_events = sorted(events, key=lambda e: e.viral_score, reverse=True)
        peak_moments = [
            {
                "time": e.start_time,
                "type": e.event_type.value,
                "viral_score": e.viral_score,
                "confidence": e.confidence
            }
            for e in sorted_events[:10]
        ]

        return {
            "total_events": len(events),
            "event_counts": event_counts,
            "average_viral_score": total_viral_score,
            "peak_moments": peak_moments,
            "duration": duration,
            "average_energy": avg_energy,
            "has_laughter": AudioEventType.LAUGHTER.value in event_counts,
            "has_cheering": AudioEventType.CHEER.value in event_counts or AudioEventType.APPLAUSE.value in event_counts,
            "has_excitement": AudioEventType.SPEECH_EXCITEMENT.value in event_counts or AudioEventType.SCREAM.value in event_counts,
        }

    def get_events_for_segment(
        self,
        analysis_result: AudioAnalysisResult,
        start_time: float,
        end_time: float
    ) -> dict[str, Any]:
        """
        Get audio event data for a specific segment.

        Returns score contribution and tags based on detected events.
        """
        segment_events = [
            e for e in analysis_result.events
            if start_time <= e.start_time <= end_time or
               start_time <= e.end_time <= end_time
        ]

        if not segment_events:
            return {
                "audio_event_score": 0,
                "audio_tags": [],
                "peak_event": None,
                "event_count": 0
            }

        # Calculate average viral score
        avg_viral = sum(e.viral_score for e in segment_events) / len(segment_events)

        # Find peak event
        peak_event = max(segment_events, key=lambda e: e.viral_score)

        # Generate tags
        event_types = {e.event_type.value for e in segment_events}
        tags = [f"audio_{t}" for t in event_types]

        # Score scaled to 0-15 (to match virality scoring)
        audio_score = avg_viral * 15

        return {
            "audio_event_score": audio_score,
            "audio_tags": tags,
            "peak_event": peak_event.event_type.value,
            "peak_viral_score": peak_event.viral_score,
            "event_count": len(segment_events)
        }

