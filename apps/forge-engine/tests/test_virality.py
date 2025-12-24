"""Tests for virality scoring service."""

import pytest
from forge_engine.services.virality import ViralityScorer


class TestViralityScorer:
    """Tests for the ViralityScorer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scorer = ViralityScorer()
    
    def test_weights_sum_to_100(self):
        """Verify scoring weights sum to 100."""
        total = sum(self.scorer.WEIGHTS.values())
        assert total == 100, f"Weights should sum to 100, got {total}"
    
    def test_score_segment_returns_all_components(self):
        """Verify score contains all required components."""
        segment = {
            "transcript": "Test segment content",
            "transcript_segments": [
                {"start": 0, "end": 5, "text": "Test segment content"}
            ],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        score = self.scorer._score_segment(segment)
        
        assert "total" in score
        assert "hook_strength" in score
        assert "payoff" in score
        assert "humour_reaction" in score
        assert "tension_surprise" in score
        assert "clarity_autonomy" in score
        assert "rhythm" in score
        assert "reasons" in score
        assert "tags" in score
    
    def test_score_total_within_bounds(self):
        """Verify total score is between 0 and 100."""
        segment = {
            "transcript": "Non mais attends c'est incroyable! Regarde ça!",
            "transcript_segments": [
                {"start": 0, "end": 5, "text": "Non mais attends c'est incroyable!", "is_potential_hook": True, "hook_score": 5}
            ],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        score = self.scorer._score_segment(segment)
        
        assert 0 <= score["total"] <= 100
    
    def test_hook_detection_french_patterns(self):
        """Verify French hook patterns are detected."""
        segment = {
            "transcript": "non mais attends c'est dingue wesh j'te jure",
            "transcript_segments": [],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        score = self.scorer._score_segment(segment)
        
        assert score["hook_strength"] > 0
        assert len([r for r in score["reasons"] if "Hook" in r]) > 0
    
    def test_hook_detection_questions(self):
        """Verify questions boost hook score."""
        segment_question = {
            "transcript": "Tu as vu ce qui s'est passé?",
            "transcript_segments": [],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        segment_statement = {
            "transcript": "J'ai vu ce qui s'est passé.",
            "transcript_segments": [],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        score_q = self.scorer._score_segment(segment_question)
        score_s = self.scorer._score_segment(segment_statement)
        
        assert score_q["hook_strength"] > score_s["hook_strength"]
    
    def test_humor_tag_detection(self):
        """Verify humor patterns are tagged."""
        segment = {
            "transcript": "mdr c'est trop drôle lol 😂",
            "transcript_segments": [],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        score = self.scorer._score_segment(segment)
        
        assert "humour" in score["tags"]
    
    def test_optimal_duration_bonus(self):
        """Verify optimal duration (25-35s) gets payoff bonus."""
        segment_optimal = {
            "transcript": "Test content",
            "transcript_segments": [],
            "start_time": 0,
            "end_time": 30,
            "duration": 30,
        }
        
        segment_long = {
            "transcript": "Test content",
            "transcript_segments": [],
            "start_time": 0,
            "end_time": 60,
            "duration": 60,
        }
        
        score_opt = self.scorer._score_segment(segment_optimal)
        score_long = self.scorer._score_segment(segment_long)
        
        assert score_opt["payoff"] >= score_long["payoff"]
    
    def test_deduplication_removes_overlaps(self):
        """Verify overlapping segments are deduplicated."""
        segments = [
            {"start_time": 0, "end_time": 30, "score": {"total": 80}},
            {"start_time": 10, "end_time": 40, "score": {"total": 70}},  # Overlaps with first
            {"start_time": 50, "end_time": 80, "score": {"total": 60}},  # No overlap
        ]
        
        deduplicated = self.scorer.deduplicate_segments(segments, iou_threshold=0.3)
        
        # Should keep the highest scoring non-overlapping segments
        assert len(deduplicated) == 2
        assert deduplicated[0]["score"]["total"] == 80
        assert deduplicated[1]["score"]["total"] == 60
    
    def test_iou_calculation(self):
        """Verify IoU calculation is correct."""
        seg1 = {"start_time": 0, "end_time": 10}
        seg2 = {"start_time": 5, "end_time": 15}
        
        # Overlap: 5-10 = 5 seconds
        # Union: 0-15 = 15 seconds
        # IoU: 5/15 = 0.333...
        
        iou = self.scorer._calculate_iou(seg1, seg2)
        
        assert abs(iou - 0.333) < 0.01
    
    def test_no_overlap_iou_zero(self):
        """Verify non-overlapping segments have IoU of 0."""
        seg1 = {"start_time": 0, "end_time": 10}
        seg2 = {"start_time": 20, "end_time": 30}
        
        iou = self.scorer._calculate_iou(seg1, seg2)
        
        assert iou == 0.0
    
    def test_generate_topic_label(self):
        """Verify topic label generation."""
        segment = {
            "transcript": "Voici un exemple de contenu intéressant. Et une suite.",
        }
        
        label = self.scorer._generate_topic_label(segment)
        
        assert len(label) <= 43  # 40 + "..."
        assert label.startswith("Voici un exemple")
    
    def test_find_best_hook(self):
        """Verify best hook selection."""
        segment = {
            "transcript_segments": [
                {"text": "Normal sentence", "hook_score": 1},
                {"text": "Amazing hook moment!", "hook_score": 5},
                {"text": "Another normal one", "hook_score": 0},
            ]
        }
        
        hook = self.scorer._find_best_hook(segment)
        
        assert hook == "Amazing hook moment!"
    
    def test_cold_open_recommendation(self):
        """Verify cold open is recommended when appropriate."""
        segment = {
            "transcript_segments": [
                {"text": "Intro", "start": 0, "hook_score": 1},
                {"text": "Normal content", "start": 5, "hook_score": 0},
                {"text": "AMAZING HOOK!", "start": 10, "hook_score": 5},
                {"text": "More content", "start": 15, "hook_score": 0},
            ]
        }
        
        recommended, start_time = self.scorer._check_cold_open(segment)
        
        assert recommended is True
        assert start_time == 10


class TestHookTimeline:
    """Tests for hook timeline generation."""
    
    def setup_method(self):
        self.scorer = ViralityScorer()
    
    def test_timeline_generation(self):
        """Verify timeline is generated correctly."""
        segments = [
            {"start": 0, "hook_score": 5},
            {"start": 10, "hook_score": 3},
            {"start": 20, "hook_score": 0},
        ]
        
        timeline = self.scorer.generate_hook_timeline(segments, total_duration=30, resolution=5)
        
        assert len(timeline) == 6  # 0, 5, 10, 15, 20, 25
        assert all("time" in point and "value" in point for point in timeline)









