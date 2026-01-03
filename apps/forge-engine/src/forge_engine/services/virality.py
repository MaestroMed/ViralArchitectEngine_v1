"""Virality scoring service."""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ViralityScorer:
    """Service for scoring viral potential of video segments."""
    
    # Score weights (must sum to 100)
    WEIGHTS = {
        "hook_strength": 25,
        "payoff": 20,
        "humour_reaction": 15,
        "tension_surprise": 15,
        "clarity_autonomy": 15,
        "rhythm": 10,
    }
    
    # Hook detection patterns
    HOOK_PATTERNS = [
        # Questions
        (r"\?$", 3, "ends_with_question"),
        # French exclamations
        (r"\b(non mais|attends?|regarde|wesh|putain|bordel|oh mon dieu|c'est pas possible)\b", 2, "french_exclamation"),
        # English exclamations
        (r"\b(wait|oh my god|holy|no way|what the|insane|crazy)\b", 2, "english_exclamation"),
        # Direct address
        (r"\b(tu sais|vous savez|écoute|listen|check this|watch this)\b", 2, "direct_address"),
        # Setup phrases
        (r"\b(alors|donc|en fait|basically|so basically)\b", 1, "setup_phrase"),
    ]
    
    # Content tags
    CONTENT_PATTERNS = [
        (r"\b(mdr|lol|ptdr|haha|😂|🤣)\b", "humour"),
        (r"\b(incroyable|dingue|ouf|insane|crazy|unbelievable)\b", "surprise"),
        (r"\b(rage|énervé|angry|pissed|furieux)\b", "rage"),
        (r"\b(clutch|win|gg|let's go|victory)\b", "clutch"),
        (r"\b(débat|argument|versus|vs|contre)\b", "debate"),
        (r"\b(fail|rip|mort|dead|f in chat)\b", "fail"),
    ]
    
    def __init__(self):
        # Clip duration range: 30s to 3min30
        self.min_duration = 30       # Minimum 30s
        self.max_duration = 210      # Max 3min30
        self.optimal_duration = 60   # Sweet spot for TikTok
        self.target_durations = [30, 45, 60, 75, 90, 120, 150, 180, 210]  # Sliding windows
    
    def generate_segments(
        self,
        transcript_segments: List[Dict[str, Any]],
        total_duration: float,
        audio_data: Optional[Dict[str, Any]] = None,
        scene_data: Optional[Dict[str, Any]] = None,
        window_sizes: List[int] = None
    ) -> List[Dict[str, Any]]:
        """Generate candidate segments using sliding windows optimized for TikTok monetization."""
        if not transcript_segments:
            return []
        
        # Use target durations for TikTok monetization (60s minimum)
        if window_sizes is None:
            window_sizes = self.target_durations  # [60, 75, 90, 120, 150, 180]
        
        candidates = []
        scene_times = []
        
        # Get scene change times for natural break points
        if scene_data:
            scene_times = [s.get("time", 0) for s in scene_data.get("scenes", [])]
        
        for window_size in window_sizes:
            step = window_size // 3  # 33% overlap for better coverage
            
            current_time = 0
            while current_time + window_size <= total_duration:
                # Find transcript segments in this window
                window_transcripts = [
                    seg for seg in transcript_segments
                    if seg["start"] >= current_time and seg["end"] <= current_time + window_size
                ]
                
                if window_transcripts:
                    # Snap to sentence boundaries
                    start_time = window_transcripts[0]["start"]
                    end_time = window_transcripts[-1]["end"]
                    
                    # Try to extend to natural break points (scene changes, pauses)
                    end_time = self._find_natural_end(
                        end_time, 
                        transcript_segments, 
                        scene_times, 
                        self.min_duration, 
                        self.max_duration
                    )
                    
                    duration = end_time - start_time
                    
                    # Ensure minimum duration for monetization
                    if duration >= self.min_duration:
                        # Get final transcript for the adjusted duration
                        final_transcripts = [
                            seg for seg in transcript_segments
                            if seg["start"] >= start_time and seg["end"] <= end_time
                        ]
                        
                        candidates.append({
                            "start_time": start_time,
                            "end_time": end_time,
                            "duration": duration,
                            "transcript_segments": final_transcripts,
                            "transcript": " ".join(s["text"] for s in final_transcripts),
                            "window_size": window_size,
                        })
                
                current_time += step
        
        logger.info("Generated %d candidate segments (min %ds, target %ds)", 
                    len(candidates), self.min_duration, self.optimal_duration)
        return candidates
    
    def _find_natural_end(
        self, 
        current_end: float, 
        transcript_segments: List[Dict],
        scene_times: List[float],
        min_duration: float,
        max_duration: float
    ) -> float:
        """Find a natural ending point (pause, scene change, sentence end)."""
        # Look for scene changes near the current end
        for scene_time in scene_times:
            if current_end - 5 <= scene_time <= current_end + 10:
                return scene_time
        
        # Look for long pauses in transcript
        for i, seg in enumerate(transcript_segments):
            if seg["start"] > current_end + 10:
                break
            if seg["start"] > current_end - 5:
                # Check for pause before this segment
                if i > 0:
                    prev_end = transcript_segments[i-1]["end"]
                    gap = seg["start"] - prev_end
                    if gap > 1.0:  # 1+ second pause
                        return prev_end
        
        return current_end
    
    def score_segments(
        self,
        segments: List[Dict[str, Any]],
        transcript_data: Optional[Dict[str, Any]] = None,
        audio_data: Optional[Dict[str, Any]] = None,
        scene_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Score all candidate segments."""
        scored = []
        
        for segment in segments:
            score = self._score_segment(segment, audio_data, scene_data)
            segment["score"] = score
            segment["topic_label"] = self._generate_topic_label(segment)
            segment["hook_text"] = self._find_best_hook(segment)
            segment["cold_open_recommended"], segment["cold_open_start_time"] = \
                self._check_cold_open(segment)
            scored.append(segment)
        
        # Sort by total score
        scored.sort(key=lambda x: x["score"]["total"], reverse=True)
        
        return scored
    
    def _score_segment(
        self,
        segment: Dict[str, Any],
        audio_data: Optional[Dict[str, Any]] = None,
        scene_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Calculate viral score for a segment."""
        transcript = segment.get("transcript", "").lower()
        transcript_segs = segment.get("transcript_segments", [])
        
        reasons = []
        tags = set()
        
        # Hook strength (0-25)
        hook_score = 0
        for pattern, points, reason in self.HOOK_PATTERNS:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            if matches:
                hook_score += points * min(len(matches), 3)
                reasons.append(f"Hook: {reason}")
        
        # Check for strong opening
        if transcript_segs:
            first_seg = transcript_segs[0]
            if first_seg.get("is_potential_hook"):
                hook_score += 5
                reasons.append("Strong opening hook")
        
        hook_score = min(hook_score, 25)
        
        # Payoff (0-20)
        payoff_score = 0
        
        # Check for conclusion markers
        conclusion_patterns = [
            r"\b(voilà|done|that's it|boom|let's go|gg)\b",
            r"!{2,}",  # Multiple exclamation marks
        ]
        for pattern in conclusion_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                payoff_score += 5
                reasons.append("Strong conclusion")
        
        # Duration bonus for optimal length
        duration = segment.get("duration", 30)
        if 25 <= duration <= 35:
            payoff_score += 5
            reasons.append("Optimal duration")
        
        # Last segment energy
        if transcript_segs and len(transcript_segs) > 1:
            last_seg = transcript_segs[-1]
            if last_seg.get("hook_score", 0) >= 2:
                payoff_score += 5
                reasons.append("Strong ending")
        
        payoff_score = min(payoff_score, 20)
        
        # Humour/Reaction (0-15)
        humour_score = 0
        
        for pattern, tag in self.CONTENT_PATTERNS:
            if re.search(pattern, transcript, re.IGNORECASE):
                if tag == "humour":
                    humour_score += 5
                    tags.add(tag)
                    reasons.append("Contains humor markers")
                elif tag in ("surprise", "rage", "fail"):
                    humour_score += 3
                    tags.add(tag)
        
        humour_score = min(humour_score, 15)
        
        # Tension/Surprise (0-15)
        tension_score = 0
        
        # Audio energy variance (if available)
        if audio_data:
            energy = audio_data.get("energy_timeline", [])
            segment_energy = [
                e for e in energy
                if segment["start_time"] <= e.get("time", 0) <= segment["end_time"]
            ]
            if segment_energy:
                values = [e.get("value", 0) for e in segment_energy]
                if values:
                    variance = sum((v - sum(values)/len(values))**2 for v in values) / len(values)
                    if variance > 0.1:
                        tension_score += 5
                        reasons.append("High audio variance")
        
        # Scene changes
        if scene_data:
            scenes = scene_data.get("scenes", [])
            segment_scenes = [
                s for s in scenes
                if segment["start_time"] <= s.get("time", 0) <= segment["end_time"]
            ]
            if len(segment_scenes) >= 2:
                tension_score += 5
                reasons.append("Multiple scene changes")
        
        # Content tension markers
        tension_patterns = [
            r"\b(suspense|tension|stress|anxieux|nervous)\b",
            r"\b(mais|but|however|pourtant)\b",  # Contrast markers
        ]
        for pattern in tension_patterns:
            if re.search(pattern, transcript, re.IGNORECASE):
                tension_score += 3
        
        tension_score = min(tension_score, 15)
        
        # Clarity/Autonomy (0-15)
        clarity_score = 10  # Base score
        
        # Penalize if context seems needed
        context_markers = [
            r"^(donc|alors|et|and|so)\b",  # Starts with connector
            r"\b(comme je disais|as I said|earlier)\b",  # References previous
        ]
        for pattern in context_markers:
            if re.search(pattern, transcript, re.IGNORECASE):
                clarity_score -= 3
                reasons.append("May need context")
        
        # Bonus for self-contained phrases
        if len(transcript_segs) >= 3:
            clarity_score += 3
            reasons.append("Self-contained narrative")
        
        clarity_score = max(0, min(clarity_score, 15))
        
        # Rhythm (0-10)
        rhythm_score = 5  # Base score
        
        # Check speech pacing
        word_count = len(transcript.split())
        words_per_second = word_count / max(duration, 1)
        
        if 2.0 <= words_per_second <= 3.5:  # Good pacing
            rhythm_score += 3
            reasons.append("Good speech pacing")
        
        # Short punchy sentences
        sentences = re.split(r'[.!?]', transcript)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
        
        if 5 <= avg_sentence_length <= 12:
            rhythm_score += 2
            reasons.append("Punchy sentences")
        
        rhythm_score = min(rhythm_score, 10)
        
        # Calculate total
        total = hook_score + payoff_score + humour_score + tension_score + clarity_score + rhythm_score
        
        # Detect content tags
        for pattern, tag in self.CONTENT_PATTERNS:
            if re.search(pattern, transcript, re.IGNORECASE):
                tags.add(tag)
        
        return {
            "total": min(total, 100),
            "hook_strength": hook_score,
            "payoff": payoff_score,
            "humour_reaction": humour_score,
            "tension_surprise": tension_score,
            "clarity_autonomy": clarity_score,
            "rhythm": rhythm_score,
            "reasons": reasons[:5],  # Limit to top 5 reasons
            "tags": list(tags),
        }
    
    def _generate_topic_label(self, segment: Dict[str, Any]) -> str:
        """Generate a short topic label for the segment."""
        transcript = segment.get("transcript", "")
        
        # Use first sentence or phrase
        sentences = re.split(r'[.!?]', transcript)
        if sentences:
            first = sentences[0].strip()
            if len(first) > 40:
                first = first[:37] + "..."
            return first
        
        return "Segment"
    
    def _find_best_hook(self, segment: Dict[str, Any]) -> Optional[str]:
        """Find the best hook text in the segment."""
        transcript_segs = segment.get("transcript_segments", [])
        
        if not transcript_segs:
            return None
        
        # Find segment with highest hook score
        best_hook = max(transcript_segs, key=lambda x: x.get("hook_score", 0))
        
        if best_hook.get("hook_score", 0) >= 2:
            return best_hook.get("text", "")
        
        return transcript_segs[0].get("text", "")
    
    def _check_cold_open(self, segment: Dict[str, Any]) -> tuple[bool, Optional[float]]:
        """Check if cold open would work for this segment."""
        transcript_segs = segment.get("transcript_segments", [])
        
        if not transcript_segs or len(transcript_segs) < 3:
            return False, None
        
        # Find best hook that's not at the start
        best_idx = 0
        best_score = 0
        
        for i, seg in enumerate(transcript_segs[1:], 1):  # Skip first
            score = seg.get("hook_score", 0)
            if score > best_score:
                best_score = score
                best_idx = i
        
        # Only recommend if we found a strong hook not at start
        if best_score >= 3 and best_idx > 0:
            return True, transcript_segs[best_idx]["start"]
        
        return False, None
    
    def deduplicate_segments(
        self,
        segments: List[Dict[str, Any]],
        iou_threshold: float = 0.5,
        max_segments: int = 20
    ) -> List[Dict[str, Any]]:
        """Remove overlapping segments, keeping higher scored ones."""
        if not segments:
            return []
        
        # Sort by score descending
        sorted_segs = sorted(segments, key=lambda x: x["score"]["total"], reverse=True)
        
        kept = []
        
        for seg in sorted_segs:
            if len(kept) >= max_segments:
                break
            
            # Check overlap with kept segments
            dominated = False
            for kept_seg in kept:
                iou = self._calculate_iou(seg, kept_seg)
                if iou > iou_threshold:
                    dominated = True
                    break
            
            if not dominated:
                kept.append(seg)
        
        return kept
    
    def _calculate_iou(self, seg1: Dict, seg2: Dict) -> float:
        """Calculate intersection over union of two segments."""
        start1, end1 = seg1["start_time"], seg1["end_time"]
        start2, end2 = seg2["start_time"], seg2["end_time"]
        
        intersection_start = max(start1, start2)
        intersection_end = min(end1, end2)
        
        if intersection_start >= intersection_end:
            return 0.0
        
        intersection = intersection_end - intersection_start
        union = (end1 - start1) + (end2 - start2) - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def generate_hook_timeline(
        self,
        transcript_segments: List[Dict[str, Any]],
        total_duration: float,
        resolution: float = 1.0
    ) -> List[Dict[str, Any]]:
        """Generate hook likelihood timeline data."""
        timeline = []
        
        current_time = 0
        while current_time < total_duration:
            # Find segments near this time
            nearby_score = 0
            for seg in transcript_segments:
                if abs(seg["start"] - current_time) < 5:  # Within 5 seconds
                    nearby_score += seg.get("hook_score", 0)
            
            timeline.append({
                "time": current_time,
                "value": min(nearby_score / 10, 1.0),  # Normalize to 0-1
            })
            
            current_time += resolution
        
        return timeline


