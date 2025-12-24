"""Tests for segment generation and overlap handling."""

import pytest
from forge_engine.services.virality import ViralityScorer


class TestSegmentGeneration:
    """Tests for segment generation logic."""
    
    def setup_method(self):
        self.scorer = ViralityScorer()
    
    def test_generates_segments_from_transcript(self):
        """Verify segments are generated from transcript."""
        transcript_segments = [
            {"start": 0, "end": 5, "text": "First sentence."},
            {"start": 5, "end": 10, "text": "Second sentence."},
            {"start": 10, "end": 15, "text": "Third sentence."},
            {"start": 15, "end": 20, "text": "Fourth sentence."},
            {"start": 20, "end": 25, "text": "Fifth sentence."},
            {"start": 25, "end": 30, "text": "Sixth sentence."},
        ]
        
        segments = self.scorer.generate_segments(
            transcript_segments,
            total_duration=30,
            window_sizes=[15]
        )
        
        assert len(segments) > 0
    
    def test_respects_minimum_duration(self):
        """Verify segments respect minimum duration."""
        self.scorer.min_duration = 15
        
        transcript_segments = [
            {"start": 0, "end": 5, "text": "Short."},
        ]
        
        segments = self.scorer.generate_segments(
            transcript_segments,
            total_duration=10,
            window_sizes=[10]
        )
        
        # Should not generate segment shorter than min_duration
        for seg in segments:
            assert seg["duration"] >= self.scorer.min_duration
    
    def test_snaps_to_sentence_boundaries(self):
        """Verify segment timing snaps to transcript boundaries."""
        transcript_segments = [
            {"start": 2.5, "end": 7.3, "text": "First."},
            {"start": 7.5, "end": 12.8, "text": "Second."},
            {"start": 13.0, "end": 18.2, "text": "Third."},
        ]
        
        segments = self.scorer.generate_segments(
            transcript_segments,
            total_duration=20,
            window_sizes=[15]
        )
        
        for seg in segments:
            # Start should match a transcript segment start
            assert any(abs(seg["start_time"] - ts["start"]) < 0.1 for ts in transcript_segments)
            # End should match a transcript segment end
            assert any(abs(seg["end_time"] - ts["end"]) < 0.1 for ts in transcript_segments)
    
    def test_includes_transcript_in_segments(self):
        """Verify generated segments include transcript data."""
        transcript_segments = [
            {"start": 0, "end": 10, "text": "Test content here."},
            {"start": 10, "end": 20, "text": "More test content."},
        ]
        
        segments = self.scorer.generate_segments(
            transcript_segments,
            total_duration=20,
            window_sizes=[20]
        )
        
        for seg in segments:
            assert "transcript" in seg
            assert "transcript_segments" in seg
            assert len(seg["transcript"]) > 0
    
    def test_multiple_window_sizes(self):
        """Verify different window sizes generate different segments."""
        transcript_segments = [
            {"start": i * 5, "end": (i + 1) * 5, "text": f"Sentence {i}"}
            for i in range(20)  # 100 seconds of content
        ]
        
        segments = self.scorer.generate_segments(
            transcript_segments,
            total_duration=100,
            window_sizes=[15, 30, 45]
        )
        
        # Should have segments of varying durations
        durations = set(int(seg["duration"]) for seg in segments)
        assert len(durations) > 1


class TestSegmentOverlap:
    """Tests for segment overlap detection."""
    
    def setup_method(self):
        self.scorer = ViralityScorer()
    
    def test_full_overlap_iou_one(self):
        """Verify identical segments have IoU of 1."""
        seg1 = {"start_time": 0, "end_time": 10}
        seg2 = {"start_time": 0, "end_time": 10}
        
        iou = self.scorer._calculate_iou(seg1, seg2)
        
        assert iou == 1.0
    
    def test_half_overlap(self):
        """Verify 50% overlap calculation."""
        seg1 = {"start_time": 0, "end_time": 10}
        seg2 = {"start_time": 5, "end_time": 15}
        
        # Overlap: 5 seconds (5-10)
        # Union: 15 seconds (0-15)
        # IoU: 5/15 = 0.333...
        
        iou = self.scorer._calculate_iou(seg1, seg2)
        
        assert abs(iou - (5/15)) < 0.001
    
    def test_contained_segment(self):
        """Verify IoU when one segment contains another."""
        seg1 = {"start_time": 0, "end_time": 30}
        seg2 = {"start_time": 10, "end_time": 20}
        
        # Overlap: 10 seconds (seg2 entirely)
        # Union: 30 seconds (seg1 entirely)
        # IoU: 10/30 = 0.333...
        
        iou = self.scorer._calculate_iou(seg1, seg2)
        
        assert abs(iou - (10/30)) < 0.001
    
    def test_dedup_keeps_highest_score(self):
        """Verify deduplication keeps highest scoring segments."""
        segments = [
            {"start_time": 0, "end_time": 20, "score": {"total": 90}},
            {"start_time": 5, "end_time": 25, "score": {"total": 80}},
            {"start_time": 10, "end_time": 30, "score": {"total": 70}},
        ]
        
        result = self.scorer.deduplicate_segments(segments, iou_threshold=0.3)
        
        # Highest score should always be first
        assert result[0]["score"]["total"] == 90
    
    def test_dedup_respects_max_segments(self):
        """Verify deduplication respects max segments limit."""
        segments = [
            {"start_time": i * 50, "end_time": (i + 1) * 50, "score": {"total": 50 - i}}
            for i in range(30)
        ]
        
        result = self.scorer.deduplicate_segments(segments, max_segments=10)
        
        assert len(result) <= 10
    
    def test_dedup_diverse_segments(self):
        """Verify deduplication preserves diverse segments."""
        segments = [
            {"start_time": 0, "end_time": 30, "score": {"total": 80}},
            {"start_time": 100, "end_time": 130, "score": {"total": 70}},
            {"start_time": 200, "end_time": 230, "score": {"total": 60}},
        ]
        
        result = self.scorer.deduplicate_segments(segments, iou_threshold=0.5)
        
        # All segments should be kept (no overlap)
        assert len(result) == 3









