"""Pytest configuration and fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_transcript_segments():
    """Sample transcript segments for testing."""
    return [
        {
            "id": 0,
            "start": 0.0,
            "end": 5.5,
            "text": "Salut tout le monde, bienvenue sur le stream!",
            "words": [
                {"word": "Salut", "start": 0.0, "end": 0.5, "confidence": 0.95},
                {"word": "tout", "start": 0.5, "end": 0.8, "confidence": 0.92},
                {"word": "le", "start": 0.8, "end": 0.9, "confidence": 0.98},
                {"word": "monde", "start": 0.9, "end": 1.3, "confidence": 0.94},
            ]
        },
        {
            "id": 1,
            "start": 5.5,
            "end": 12.0,
            "text": "Non mais attends tu as vu ce qui s'est passé?",
            "hook_score": 4,
            "is_potential_hook": True,
        },
        {
            "id": 2,
            "start": 12.0,
            "end": 18.0,
            "text": "C'est complètement dingue, j'te jure!",
            "hook_score": 3,
            "is_potential_hook": True,
        },
    ]


@pytest.fixture
def sample_audio_analysis():
    """Sample audio analysis data for testing."""
    return {
        "duration": 60.0,
        "energy_timeline": [
            {"time": i, "value": 0.5 + 0.3 * (i % 10) / 10}
            for i in range(60)
        ],
        "peaks": [
            {"time": 15.0, "value": 0.9},
            {"time": 35.0, "value": 0.85},
        ],
        "silences": [
            {"start": 25.0, "end": 27.0},
        ],
        "laughter_patterns": [
            {"time": 40.0, "confidence": 0.7},
        ],
    }


@pytest.fixture
def sample_scene_data():
    """Sample scene detection data for testing."""
    return {
        "scenes": [
            {"id": 0, "time": 0.0, "end_time": 20.0, "confidence": 0.9},
            {"id": 1, "time": 20.0, "end_time": 45.0, "confidence": 0.85},
            {"id": 2, "time": 45.0, "end_time": 60.0, "confidence": 0.8},
        ],
        "total_scenes": 3,
    }


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "id": "test-project-123",
        "name": "Test Stream",
        "source_path": "/path/to/video.mp4",
        "source_filename": "video.mp4",
        "duration": 3600.0,
        "width": 1920,
        "height": 1080,
        "fps": 30.0,
        "audio_tracks": 1,
        "status": "analyzed",
    }


@pytest.fixture
def sample_segment():
    """Sample segment for testing."""
    return {
        "id": "segment-456",
        "project_id": "test-project-123",
        "start_time": 100.0,
        "end_time": 130.0,
        "duration": 30.0,
        "topic_label": "Moment incroyable",
        "hook_text": "Non mais attends!",
        "transcript": "Non mais attends tu as vu ce qui s'est passé? C'est dingue!",
        "score": {
            "total": 75,
            "hook_strength": 20,
            "payoff": 15,
            "humour_reaction": 12,
            "tension_surprise": 10,
            "clarity_autonomy": 10,
            "rhythm": 8,
            "reasons": ["Strong hook", "Good pacing"],
            "tags": ["surprise", "humour"],
        },
        "cold_open_recommended": True,
        "cold_open_start_time": 105.0,
    }









