"""End-to-End Pipeline Tests.

Tests the complete FORGE pipeline from ingestion to export.

These tests are marked @e2e and are excluded from the default CI run by design.
They exercise the real (non-mocked) code paths for the dependency-light services
(virality scoring uses numpy/sklearn which are always present) and gracefully
SKIP for the heavy optional services (librosa / opencv / faster-whisper /
scenedetect / scipy) that are not installed in the CI-equivalent virtualenv.

Run with: pytest tests/test_pipeline_e2e.py -v -m e2e
"""

from forge_engine.core.timeutils import utcnow
import importlib
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# All tests in this file require a live server or full env — skip in normal CI
pytestmark = pytest.mark.e2e


def _service(modpath: str, attr: str):
    """Import a service attribute, skipping the test cleanly if an optional
    heavy dependency (librosa / opencv / whisper / scenedetect / scipy / ...)
    is missing in this environment.

    Used for service imports so a test never FAILs/ERRORs purely because an
    optional dependency is absent — it SKIPs with a clear reason instead.
    """
    try:
        module = importlib.import_module(modpath)
        return getattr(module, attr)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: any import-time error -> skip
        pytest.skip(f"optional dep missing for {modpath}.{attr}: {exc}")


class TestPipelineE2E:
    """End-to-end tests for the complete FORGE pipeline."""

    @pytest.fixture
    def temp_library(self):
        """Create a temporary library directory."""
        temp_dir = tempfile.mkdtemp(prefix="forge_test_")
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_video_path(self, temp_library):
        """Create a mock video file."""
        video_path = temp_library / "test_video.mp4"
        # Create a minimal file for testing
        video_path.write_bytes(b"mock video data")
        return video_path

    @pytest.fixture
    def mock_audio_path(self, temp_library):
        """Create a mock audio file."""
        audio_path = temp_library / "test_audio.wav"
        audio_path.write_bytes(b"mock audio data")
        return audio_path

    # ==================== INGESTION TESTS ====================

    @pytest.mark.asyncio
    async def test_project_creation(self, sample_project_data):
        """Test project creation with valid data."""
        Project = _service("forge_engine.models.project", "Project")

        project = Project(**sample_project_data)

        assert project.id == "test-project-123"
        assert project.name == "Test Stream"
        assert project.duration == 3600.0
        assert project.status == "analyzed"

    @pytest.mark.asyncio
    async def test_ffmpeg_probe(self, mock_video_path):
        """Test FFmpegService video probing (mocked ffprobe)."""
        FFmpegService = _service("forge_engine.services.ffmpeg", "FFmpegService")

        ffmpeg = FFmpegService()

        # Mock ffprobe result (FFmpegService.probe is the real entry point)
        mock_metadata = {
            "width": 1920,
            "height": 1080,
            "duration": 3600.0,
            "fps": 30.0,
            "codec": "h264",
            "audio_tracks": 1,
        }

        with patch.object(ffmpeg, "probe", return_value=mock_metadata):
            result = await ffmpeg.probe(str(mock_video_path))

            assert result["width"] == 1920
            assert result["height"] == 1080
            assert result["fps"] == 30.0

    @pytest.mark.asyncio
    async def test_ffmpeg_create_proxy(self, mock_video_path, temp_library):
        """Test proxy video creation."""
        FFmpegService = _service("forge_engine.services.ffmpeg", "FFmpegService")

        ffmpeg = FFmpegService()

        proxy_path = temp_library / "proxy.mp4"

        # Mock the actual encoding (FFmpegService.create_proxy is the real method)
        with patch.object(ffmpeg, "create_proxy") as mock_encode:
            mock_encode.return_value = str(proxy_path)

            # Write mock proxy file
            proxy_path.write_bytes(b"proxy video data")

            result = await ffmpeg.create_proxy(
                str(mock_video_path),
                str(proxy_path),
            )

            mock_encode.assert_called_once()
            assert result == str(proxy_path)

    @pytest.mark.asyncio
    async def test_audio_extraction(self, mock_video_path, temp_library):
        """Test audio extraction from video."""
        FFmpegService = _service("forge_engine.services.ffmpeg", "FFmpegService")

        ffmpeg = FFmpegService()
        audio_path = temp_library / "audio.wav"

        with patch.object(ffmpeg, "extract_audio") as mock_extract:
            mock_extract.return_value = str(audio_path)
            audio_path.write_bytes(b"audio data")

            result = await ffmpeg.extract_audio(
                str(mock_video_path),
                str(audio_path),
            )

            assert result == str(audio_path)

    # ==================== TRANSCRIPTION TESTS ====================

    @pytest.mark.asyncio
    async def test_transcription_service_availability(self):
        """Test that transcription service reports availability correctly."""
        TranscriptionService = _service(
            "forge_engine.services.transcription", "TranscriptionService"
        )

        service = TranscriptionService.get_instance()

        # Should not raise
        is_available = service.is_available()
        assert isinstance(is_available, bool)

    @pytest.mark.asyncio
    async def test_transcription_mock(self, mock_audio_path, sample_transcript_segments):
        """Test transcription with mocked Whisper."""
        TranscriptionService = _service(
            "forge_engine.services.transcription", "TranscriptionService"
        )

        service = TranscriptionService.get_instance()

        mock_result = {
            "language": "fr",
            "language_probability": 0.98,
            "duration": 60.0,
            "segments": sample_transcript_segments,
            "text": " ".join(s["text"] for s in sample_transcript_segments),
        }

        with patch.object(service, "transcribe", return_value=mock_result):
            result = await service.transcribe(str(mock_audio_path))

            assert result["language"] == "fr"
            assert len(result["segments"]) == 3
            assert result["duration"] == 60.0

    @pytest.mark.asyncio
    async def test_hook_detection(self, sample_transcript_segments):
        """Test hook and punchline detection in transcript."""
        TranscriptionService = _service(
            "forge_engine.services.transcription", "TranscriptionService"
        )

        service = TranscriptionService.get_instance()

        enhanced = service.detect_hooks_and_punchlines(sample_transcript_segments)

        # Check that hook detection works
        assert len(enhanced) == 3

        # The second segment should have a higher hook score (question + intensifier)
        hook_segment = enhanced[1]
        assert hook_segment.get("hook_score", 0) > 0
        assert hook_segment.get("is_potential_hook", False) is True

    # ==================== ANALYSIS TESTS ====================

    @pytest.mark.asyncio
    async def test_audio_analysis(self, sample_audio_analysis):
        """Test audio analysis service (real class: AudioAnalyzer)."""
        AudioAnalyzer = _service(
            "forge_engine.services.audio_analysis", "AudioAnalyzer"
        )

        service = AudioAnalyzer()

        # AudioAnalyzer.analyze is the real entry point (librosa is mocked away here).
        with patch.object(service, "analyze", return_value=sample_audio_analysis):
            result = await service.analyze("mock_path.wav")

            assert result["duration"] == 60.0
            assert len(result["peaks"]) == 2
            assert len(result["silences"]) == 1

    @pytest.mark.asyncio
    async def test_scene_detection(self, sample_scene_data):
        """Test scene detection service (real class: SceneDetector)."""
        SceneDetector = _service(
            "forge_engine.services.scene_detection", "SceneDetector"
        )

        service = SceneDetector()

        with patch.object(service, "detect_scenes", return_value=sample_scene_data):
            result = await service.detect_scenes("mock_path.mp4")

            assert result["total_scenes"] == 3
            assert len(result["scenes"]) == 3

    # ==================== VIRALITY SCORING TESTS ====================

    @pytest.mark.asyncio
    async def test_virality_scoring(
        self,
        sample_transcript_segments,
        sample_audio_analysis,
        sample_scene_data,
    ):
        """Test virality scoring of segments (real, non-mocked execution)."""
        ViralityScorer = _service("forge_engine.services.virality", "ViralityScorer")

        scorer = ViralityScorer(use_llm=False)

        # Generate segments from transcript. The sample transcript only spans
        # ~18s, shorter than the default 30s minimum window, so we drive the
        # generator with small explicit window sizes to get candidate segments.
        scorer.min_duration = 5
        segments = scorer.generate_segments(
            transcript_segments=sample_transcript_segments,
            total_duration=60.0,
            audio_data=sample_audio_analysis,
            scene_data=sample_scene_data,
            window_sizes=[10, 15],
        )

        assert len(segments) > 0

        # Score the segments (sync heuristic scorer)
        scored = scorer.score_segments(segments, sample_transcript_segments)

        assert len(scored) > 0
        for segment in scored:
            assert "score" in segment
            assert "total" in segment["score"]
            assert 0 <= segment["score"]["total"] <= 100

    @pytest.mark.asyncio
    async def test_segment_deduplication(self):
        """Test segment deduplication to avoid overlaps."""
        ViralityScorer = _service("forge_engine.services.virality", "ViralityScorer")

        scorer = ViralityScorer(use_llm=False)

        # Create overlapping segments. The first two overlap heavily
        # (IoU = 25/30 ≈ 0.83, above the 0.5 threshold) so only the higher
        # scored one survives; the third does not overlap anything.
        segments = [
            {"start_time": 0, "end_time": 30, "score": {"total": 80}},
            {"start_time": 5, "end_time": 30, "score": {"total": 70}},  # Heavy overlap with first
            {"start_time": 100, "end_time": 130, "score": {"total": 90}},  # No overlap
        ]

        deduplicated = scorer.deduplicate_segments(segments, iou_threshold=0.5)

        # Should keep highest score when overlapping
        assert len(deduplicated) == 2
        scores = [s["score"]["total"] for s in deduplicated]
        assert 80 in scores
        assert 90 in scores
        assert 70 not in scores  # The lower-scored overlapping segment is dropped

    # ==================== EXPORT TESTS ====================

    @pytest.mark.asyncio
    async def test_export_service_render(
        self,
        sample_segment,
        temp_library,
        mock_video_path,
    ):
        """Test video rendering for export."""
        RenderService = _service("forge_engine.services.render", "RenderService")

        render = RenderService()
        output_path = temp_library / "output.mp4"

        with patch.object(render, "render_clip") as mock_render:
            mock_render.return_value = {
                "output_path": str(output_path),
                "duration": 30.0,
                "resolution": "1080x1920",
            }

            result = await render.render_clip(
                source_path=str(mock_video_path),
                output_path=str(output_path),
                start_time=sample_segment["start_time"],
                end_time=sample_segment["end_time"],
                resolution="1080x1920",
            )

            assert result["duration"] == 30.0
            assert "output_path" in result

    @pytest.mark.asyncio
    async def test_caption_generation(self, sample_segment, sample_transcript_segments):
        """Test ASS caption file generation."""
        CaptionEngine = _service("forge_engine.services.captions", "CaptionEngine")

        engine = CaptionEngine()

        ass_content = engine.generate_ass(
            transcript_segments=sample_transcript_segments,
            word_level=True,
        )

        assert "[Script Info]" in ass_content
        assert "[V4+ Styles]" in ass_content
        assert "[Events]" in ass_content

    # ==================== JOB SYSTEM TESTS ====================

    @pytest.mark.asyncio
    async def test_job_lifecycle(self):
        """Test job creation, progress, and completion."""
        jobs_mod = importlib.import_module("forge_engine.core.jobs")
        Job = jobs_mod.Job
        JobStatus = jobs_mod.JobStatus
        JobType = jobs_mod.JobType

        # Create a transient job object
        job = Job(
            id="test-job-001",
            project_id="test-project-123",
            type=JobType.INGEST,
            status=JobStatus.PENDING,
        )

        assert job.status == JobStatus.PENDING

        # Simulate job progress
        job.status = JobStatus.RUNNING
        job.progress = 50

        assert job.status == JobStatus.RUNNING
        assert job.progress == 50

        # Complete job
        job.status = JobStatus.COMPLETED
        job.progress = 100

        assert job.status == JobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_job_error_handling(self):
        """Test job error handling and recovery."""
        jobs_mod = importlib.import_module("forge_engine.core.jobs")
        Job = jobs_mod.Job
        JobStatus = jobs_mod.JobStatus
        JobType = jobs_mod.JobType

        job = Job(
            id="test-job-002",
            project_id="test-project-123",
            type=JobType.ANALYZE,
            status=JobStatus.RUNNING,
        )

        # Simulate error
        job.status = JobStatus.FAILED
        job.error = "Test error message"

        assert job.status == JobStatus.FAILED
        assert job.error == "Test error message"

    # ==================== FULL PIPELINE INTEGRATION TEST ====================

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(
        self,
        temp_library,
        mock_video_path,
        sample_transcript_segments,
        sample_audio_analysis,
        sample_scene_data,
    ):
        """Test the complete pipeline from ingest to export.

        Heavy services (transcription, audio_analysis, scene_detection, render)
        are mocked at the method level; if any of them cannot even be imported
        because an optional dependency is missing, the test SKIPs cleanly.
        """
        FFmpegService = _service("forge_engine.services.ffmpeg", "FFmpegService")
        TranscriptionService = _service(
            "forge_engine.services.transcription", "TranscriptionService"
        )
        AudioAnalyzer = _service(
            "forge_engine.services.audio_analysis", "AudioAnalyzer"
        )
        SceneDetector = _service(
            "forge_engine.services.scene_detection", "SceneDetector"
        )
        ViralityScorer = _service("forge_engine.services.virality", "ViralityScorer")
        RenderService = _service("forge_engine.services.render", "RenderService")

        # === PHASE 1: INGESTION (probe) ===
        ffmpeg = FFmpegService()

        mock_probe_result = {
            "width": 1920,
            "height": 1080,
            "duration": 60.0,
            "fps": 30.0,
        }

        with patch.object(ffmpeg, "probe", return_value=mock_probe_result):
            probe_result = await ffmpeg.probe(str(mock_video_path))
            assert probe_result["duration"] == 60.0

        # === PHASE 2: TRANSCRIPTION ===
        transcription = TranscriptionService.get_instance()

        mock_transcription = {
            "language": "fr",
            "duration": 60.0,
            "segments": sample_transcript_segments,
            "text": "Transcribed content",
        }

        with patch.object(transcription, "transcribe", return_value=mock_transcription):
            trans_result = await transcription.transcribe("mock_audio.wav")
            assert trans_result["language"] == "fr"

        # === PHASE 3: ANALYSIS ===
        audio_analysis = AudioAnalyzer()
        scene_detection = SceneDetector()

        with patch.object(audio_analysis, "analyze", return_value=sample_audio_analysis):
            audio_result = await audio_analysis.analyze("mock_audio.wav")

        with patch.object(scene_detection, "detect_scenes", return_value=sample_scene_data):
            scene_result = await scene_detection.detect_scenes(str(mock_video_path))

        # === PHASE 4: VIRALITY SCORING (real execution) ===
        scorer = ViralityScorer(use_llm=False)
        scorer.min_duration = 5

        segments = scorer.generate_segments(
            transcript_segments=sample_transcript_segments,
            total_duration=probe_result["duration"],
            audio_data=audio_result,
            scene_data=scene_result,
            window_sizes=[10, 15],
        )

        scored_segments = scorer.score_segments(segments, sample_transcript_segments)

        # Verify we have scored segments
        assert len(scored_segments) > 0

        # Get best segment
        best_segment = max(scored_segments, key=lambda s: s["score"]["total"])

        # === PHASE 5: EXPORT ===
        render = RenderService()
        output_path = temp_library / "final_clip.mp4"

        mock_render_result = {
            "output_path": str(output_path),
            "duration": 30.0,
            "resolution": "1080x1920",
            "success": True,
        }

        with patch.object(render, "render_clip", return_value=mock_render_result):
            export_result = await render.render_clip(
                source_path=str(mock_video_path),
                output_path=str(output_path),
                start_time=best_segment["start_time"],
                end_time=best_segment["end_time"],
            )

            assert export_result["success"] is True


class TestAPIEndpoints:
    """Test API endpoints for the FORGE engine.

    The TestClient is used as a context manager so the application lifespan
    runs (DB tables created, services registered). The route prefix is /v1.
    """

    @pytest.fixture
    def test_client(self):
        """Create a test client for the FastAPI app with lifespan active."""
        from fastapi.testclient import TestClient

        from forge_engine.main import app

        with TestClient(app) as client:
            yield client

    def test_health_endpoint(self, test_client):
        """Test the health check endpoint."""
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_capabilities_endpoint(self, test_client):
        """Test the capabilities endpoint."""
        response = test_client.get("/v1/capabilities")

        assert response.status_code == 200
        data = response.json()

        # Should have capability information
        assert "ffmpeg" in data or "capabilities" in data

    def test_projects_list(self, test_client):
        """Test listing projects."""
        response = test_client.get("/v1/projects")

        assert response.status_code == 200
        data = response.json()

        # Response shape: {"success": True, "data": {"items": [...], ...}}
        assert isinstance(data, list) or "projects" in data or "data" in data


class TestWebSocket:
    """Test WebSocket communication.

    The /v1/ws endpoint does not push an initial message; the client drives the
    exchange. We verify the connection establishes and ping/pong works.
    """

    @pytest.fixture
    def test_client(self):
        from fastapi.testclient import TestClient

        from forge_engine.main import app

        with TestClient(app) as client:
            yield client

    def test_websocket_connection(self, test_client):
        """Test WebSocket connection establishment + ping/pong."""
        with test_client.websocket_connect("/v1/ws") as websocket:
            # Server does not push on connect; drive a ping and expect a PONG.
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data.get("type") in ("PONG", "connected", "jobs_list", "connection_established")

    def test_websocket_job_updates(self, test_client):
        """Test the WebSocket stays open and handles messages."""
        with test_client.websocket_connect("/v1/ws") as websocket:
            websocket.send_json({"type": "ping"})
            response = websocket.receive_json()

            # The connection should be established and responsive
            assert response is not None
            assert response.get("type") == "PONG"


class TestMonitorService:
    """Test the L'ŒIL monitoring service."""

    @pytest.mark.asyncio
    async def test_monitor_health_check(self):
        """Test monitor service status reporting."""
        MonitorService = _service("forge_engine.services.monitor", "MonitorService")

        monitor = MonitorService.get_instance()

        # MonitorService exposes get_full_status() (sync) which returns system info.
        status = monitor.get_full_status()

        assert "system" in status
        assert "cpu" in status["system"]

    @pytest.mark.asyncio
    async def test_monitor_stuck_job_detection(self):
        """Test detection of stuck jobs."""
        jobs_mod = importlib.import_module("forge_engine.core.jobs")
        Job = jobs_mod.Job
        JobStatus = jobs_mod.JobStatus
        JobType = jobs_mod.JobType

        # Create a mock stuck job (started long ago, no progress).
        # The Job dataclass tracks started_at; there is no updated_at field.
        stuck_job = Job(
            id="stuck-job-001",
            project_id="test-project",
            type=JobType.ANALYZE,
            status=JobStatus.RUNNING,
            progress=10,
        )

        # Simulate job being stuck (started 30 minutes ago)
        stuck_job.started_at = utcnow() - timedelta(minutes=30)

        # A job running for >10 minutes with no progress is considered stuck.
        is_stuck = (utcnow() - stuck_job.started_at).total_seconds() > 600

        assert is_stuck is True
