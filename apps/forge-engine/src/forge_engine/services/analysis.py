"""Analysis service for viral moment detection."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import Job, JobManager
from forge_engine.models import Project, Segment
from forge_engine.services.transcription import TranscriptionService

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
def _get_virality_scorer():
    from forge_engine.services.virality import ViralityScorer
    return ViralityScorer()

def _get_layout_engine():
    from forge_engine.services.layout import LayoutEngine
    return LayoutEngine()

def _get_audio_analyzer():
    try:
        from forge_engine.services.audio_analysis import AudioAnalyzer
        return AudioAnalyzer()
    except ImportError:
        return None

def _get_scene_detector():
    try:
        from forge_engine.services.scene_detection import SceneDetector
        return SceneDetector()
    except ImportError:
        return None


class AnalysisService:
    """Service for analyzing videos and detecting viral moments."""
    
    def __init__(self):
        self.transcription = TranscriptionService()
        self._virality = None
        self._layout = None
        self._audio_analyzer = None
        self._scene_detector = None
    
    @property
    def virality(self):
        if self._virality is None:
            self._virality = _get_virality_scorer()
        return self._virality
    
    @property
    def layout(self):
        if self._layout is None:
            self._layout = _get_layout_engine()
        return self._layout
    
    @property
    def audio_analyzer(self):
        if self._audio_analyzer is None:
            self._audio_analyzer = _get_audio_analyzer()
        return self._audio_analyzer
    
    @property
    def scene_detector(self):
        if self._scene_detector is None:
            self._scene_detector = _get_scene_detector()
        return self._scene_detector
    
    async def run_analysis(
        self,
        job: Job,
        project_id: Optional[str] = None,
        transcribe: bool = True,
        whisper_model: str = "large-v3",
        language: Optional[str] = None,
        detect_scenes: bool = True,
        analyze_audio: bool = True,
        detect_faces: bool = True,
        score_segments: bool = True,
        custom_dictionary: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run the analysis pipeline."""
        job_manager = JobManager.get_instance()
        
        # Use job.project_id if project_id not provided
        project_id = project_id or job.project_id
        if not project_id:
            raise ValueError("No project_id provided")
        
        async with async_session_maker() as db:
            # Get project
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            
            if not project:
                raise ValueError(f"Project not found: {project_id}")
            
            if not project.audio_path:
                raise ValueError("Project must be ingested first (audio required)")
            
            project_dir = settings.LIBRARY_PATH / "projects" / project_id
            analysis_dir = project_dir / "analysis"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize results
            transcript_data = None
            scene_data = None
            audio_data = None
            facecam_data = None
            segments = []
            timeline_layers = []
            
            # Helper to check if step is already done
            def load_cached_step(filename: str) -> dict | None:
                """Load cached step result if exists."""
                path = analysis_dir / filename
                if path.exists():
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            if "error" not in data:
                                logger.info("✓ Loaded cached: %s", filename)
                                return data
                    except Exception:
                        pass
                return None
            
            # Step 1: Transcription
            if transcribe:
                # Check if already done
                cached = load_cached_step("transcript.json")
                if cached:
                    transcript_data = cached
                    job_manager.update_progress(job, 35, "transcription", "Transcription déjà effectuée ✓")
                else:
                    job_manager.update_progress(job, 5, "transcription", "Transcribing audio...")
                    
                    def transcribe_progress(p):
                        job_manager.update_progress(job, 5 + p * 0.3, "transcription", f"Transcribing: {p:.0f}%")
                    
                    try:
                        transcript_data = await self.transcription.transcribe(
                            project.audio_path,
                            language=language,
                            word_timestamps=True,
                            custom_dictionary=custom_dictionary,
                            progress_callback=transcribe_progress
                        )
                        
                        # Detect hooks
                        transcript_data["segments"] = self.transcription.detect_hooks_and_punchlines(
                            transcript_data["segments"]
                        )
                        
                        # Save transcript immediately
                        with open(analysis_dir / "transcript.json", "w", encoding="utf-8") as f:
                            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
                        logger.info("✓ Saved transcript.json")
                        
                    except Exception as e:
                        logger.exception("Transcription failed: %s", e)
                        transcript_data = {"segments": [], "text": "", "error": str(e)}
            
            # Step 2: Audio analysis
            if analyze_audio and self.audio_analyzer:
                cached = load_cached_step("audio_analysis.json")
                if cached:
                    audio_data = cached
                    job_manager.update_progress(job, 50, "audio_analysis", "Analyse audio déjà effectuée ✓")
                    timeline_layers.append({
                        "id": "audio_energy",
                        "name": "Audio Energy",
                        "type": "audio_energy",
                        "data": audio_data.get("energy_timeline", []),
                        "color": "#FF6B6B"
                    })
                else:
                    job_manager.update_progress(job, 40, "audio_analysis", "Analyzing audio...")
                    
                    try:
                        audio_data = await self.audio_analyzer.analyze(
                            project.audio_path,
                            progress_callback=lambda p: job_manager.update_progress(
                                job, 40 + p * 0.1, "audio_analysis", f"Analyzing audio: {p:.0f}%"
                            )
                        )
                        
                        # Add to timeline layers
                        timeline_layers.append({
                            "id": "audio_energy",
                            "name": "Audio Energy",
                            "type": "audio_energy",
                            "data": audio_data.get("energy_timeline", []),
                            "color": "#FF6B6B"
                        })
                        
                        # Save audio analysis
                        with open(analysis_dir / "audio_analysis.json", "w") as f:
                            json.dump(audio_data, f, indent=2)
                        logger.info("✓ Saved audio_analysis.json")
                        
                    except Exception as e:
                        logger.exception("Audio analysis failed: %s", e)
                        audio_data = {"error": str(e)}
            elif analyze_audio:
                logger.warning("Audio analyzer not available, skipping")
            
            # Step 3: Scene detection
            if detect_scenes and self.scene_detector:
                cached = load_cached_step("scenes.json")
                if cached:
                    scene_data = cached
                    job_manager.update_progress(job, 65, "scene_detection", "Détection scènes déjà effectuée ✓")
                    timeline_layers.append({
                        "id": "scene_changes",
                        "name": "Scene Changes",
                        "type": "scene_changes",
                        "data": [{"time": s["time"], "value": s["confidence"]} for s in scene_data.get("scenes", [])],
                        "color": "#4ECDC4"
                    })
                else:
                    job_manager.update_progress(job, 55, "scene_detection", "Detecting scenes...")
                    
                    video_path = project.proxy_path or project.source_path
                    
                    try:
                        scene_data = await self.scene_detector.detect_scenes(
                            video_path,
                            progress_callback=lambda p: job_manager.update_progress(
                                job, 55 + p * 0.1, "scene_detection", f"Detecting scenes: {p:.0f}%"
                            )
                        )
                        
                        # Add to timeline layers
                        timeline_layers.append({
                            "id": "scene_changes",
                            "name": "Scene Changes",
                            "type": "scene_changes",
                            "data": [{"time": s["time"], "value": s["confidence"]} for s in scene_data.get("scenes", [])],
                            "color": "#4ECDC4"
                        })
                        
                        # Save scene data
                        with open(analysis_dir / "scenes.json", "w") as f:
                            json.dump(scene_data, f, indent=2)
                        logger.info("✓ Saved scenes.json")
                        
                    except Exception as e:
                        logger.exception("Scene detection failed: %s", e)
                        scene_data = {"scenes": [], "error": str(e)}
            elif detect_scenes:
                logger.warning("Scene detector not available, skipping")
            
            # Step 4: Face/Layout detection
            if detect_faces:
                cached = load_cached_step("layout.json")
                if cached:
                    facecam_data = cached
                    job_manager.update_progress(job, 80, "face_detection", "Détection layout déjà effectuée ✓")
                else:
                    job_manager.update_progress(job, 70, "face_detection", "Detecting faces and layout...")
                    
                    video_path = project.proxy_path or project.source_path
                    
                    try:
                        facecam_data = await self.layout.detect_layout(
                            video_path,
                            project.duration or 0,
                            progress_callback=lambda p: job_manager.update_progress(
                                job, 70 + p * 0.1, "face_detection", f"Detecting layout: {p:.0f}%"
                            )
                        )
                        
                        # Save layout data
                        with open(analysis_dir / "layout.json", "w") as f:
                            json.dump(facecam_data, f, indent=2)
                        logger.info("✓ Saved layout.json")
                        
                    except Exception as e:
                        logger.exception("Face detection failed: %s", e)
                        facecam_data = {"layout_type": "montage", "error": str(e)}
            
            # Step 5: Generate and score segments
            if score_segments and transcript_data:
                job_manager.update_progress(job, 85, "scoring", "Scoring viral potential...")
                
                # Generate candidate segments
                candidate_segments = self.virality.generate_segments(
                    transcript_data.get("segments", []),
                    project.duration or 0,
                    audio_data=audio_data,
                    scene_data=scene_data
                )
                
                # Score segments
                scored_segments = self.virality.score_segments(
                    candidate_segments,
                    transcript_data=transcript_data,
                    audio_data=audio_data,
                    scene_data=scene_data
                )
                
                # Deduplicate overlapping segments
                final_segments = self.virality.deduplicate_segments(scored_segments)
                
                # Store segments in database
                for seg_data in final_segments:
                    segment = Segment(
                        project_id=project_id,
                        start_time=seg_data["start_time"],
                        end_time=seg_data["end_time"],
                        duration=seg_data["duration"],
                        topic_label=seg_data.get("topic_label"),
                        hook_text=seg_data.get("hook_text"),
                        transcript=seg_data.get("transcript"),
                        transcript_segments=seg_data.get("transcript_segments"),
                        score_total=seg_data["score"]["total"],
                        score_hook=seg_data["score"]["hook_strength"],
                        score_payoff=seg_data["score"]["payoff"],
                        score_humour=seg_data["score"]["humour_reaction"],
                        score_tension=seg_data["score"]["tension_surprise"],
                        score_clarity=seg_data["score"]["clarity_autonomy"],
                        score_rhythm=seg_data["score"]["rhythm"],
                        score_reasons=seg_data["score"]["reasons"],
                        score_tags=seg_data["score"]["tags"],
                        cold_open_recommended=seg_data.get("cold_open_recommended", False),
                        cold_open_start_time=seg_data.get("cold_open_start_time"),
                        layout_type=facecam_data.get("layout_type") if facecam_data else None,
                        facecam_rect=facecam_data.get("facecam_rect") if facecam_data else None,
                        content_rect=facecam_data.get("content_rect") if facecam_data else None,
                    )
                    db.add(segment)
                    segments.append(segment)
                
                await db.commit()
                
                # Add hook likelihood to timeline
                timeline_layers.append({
                    "id": "hook_likelihood",
                    "name": "Hook Likelihood",
                    "type": "hook_likelihood",
                    "data": self.virality.generate_hook_timeline(
                        transcript_data.get("segments", []),
                        project.duration or 0
                    ),
                    "color": "#FFE66D"
                })
            
            # Save timeline data
            timeline_data = {
                "projectId": project_id,
                "duration": project.duration or 0,
                "layers": timeline_layers,
                "segments": [
                    {
                        "id": s.id,
                        "startTime": s.start_time,
                        "endTime": s.end_time,
                        "score": s.score_total,
                        "label": s.topic_label,
                    }
                    for s in segments
                ],
                "sceneChanges": scene_data.get("scenes", []) if scene_data else [],
            }
            
            with open(analysis_dir / "timeline.json", "w") as f:
                json.dump(timeline_data, f, indent=2)
            
            # Update project status
            project.status = "analyzed"
            await db.commit()
            
            job_manager.update_progress(job, 100, "complete", f"Analysis complete - {len(segments)} segments found")
            
            return {
                "project_id": project_id,
                "segments_count": len(segments),
                "timeline_layers": len(timeline_layers),
                "transcript_available": transcript_data is not None,
            }

