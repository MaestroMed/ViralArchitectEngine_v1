"""Analysis service for viral moment detection."""

import asyncio
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import Job, JobManager
from forge_engine.models import Project, Segment
from forge_engine.services.dictionary import get_dictionary_service
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
        project_id: str | None = None,
        transcribe: bool = True,
        whisper_model: str = "large-v3",
        language: str | None = None,  # None = use settings.WHISPER_LANGUAGE
        detect_scenes: bool = True,
        analyze_audio: bool = True,
        detect_faces: bool = True,
        score_segments: bool = True,
        custom_dictionary: list[str] | None = None,
        dictionary_name: str | None = None  # Named dictionary (e.g. "etostark")
    ) -> dict[str, Any]:
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
                        with open(path, encoding="utf-8") as f:
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
                        # Use configured language if not specified
                        transcribe_language = language or settings.WHISPER_LANGUAGE
                        logger.info("Transcribing with language: %s", transcribe_language)

                        # Load dictionary if specified
                        whisper_prompt = None
                        dict_hotwords = []
                        if dictionary_name:
                            dict_service = get_dictionary_service()
                            whisper_prompt = dict_service.get_whisper_prompt(dictionary_name)
                            dict_hotwords = dict_service.get_hotwords(dictionary_name)
                            logger.info("Using dictionary '%s' with %d hotwords", dictionary_name, len(dict_hotwords))

                        # Merge custom_dictionary with hotwords from named dictionary
                        all_dictionary = list(set((custom_dictionary or []) + dict_hotwords))

                        transcript_data = await self.transcription.transcribe(
                            project.audio_path,
                            language=transcribe_language,
                            word_timestamps=True,
                            initial_prompt=whisper_prompt,
                            custom_dictionary=all_dictionary if all_dictionary else None,
                            progress_callback=transcribe_progress
                        )

                        # Apply dictionary corrections to transcript
                        if dictionary_name and transcript_data.get("segments"):
                            dict_service = get_dictionary_service()
                            for segment in transcript_data["segments"]:
                                # Correct segment text
                                if segment.get("text"):
                                    segment["text"] = dict_service.apply_corrections(
                                        segment["text"], dictionary_name
                                    )
                                # Correct word-level timing
                                if segment.get("words"):
                                    segment["words"] = dict_service.apply_corrections_to_words(
                                        segment["words"], dictionary_name
                                    )
                            # Correct full text
                            if transcript_data.get("text"):
                                transcript_data["text"] = dict_service.apply_corrections(
                                    transcript_data["text"], dictionary_name
                                )
                            logger.info("Applied dictionary corrections to transcript")

                        # Validate transcription result
                        if not transcript_data or not transcript_data.get("segments"):
                            raise ValueError("Transcription returned empty result")

                        # Detect hooks
                        transcript_data["segments"] = self.transcription.detect_hooks_and_punchlines(
                            transcript_data["segments"]
                        )

                        # Save transcript immediately
                        with open(analysis_dir / "transcript.json", "w", encoding="utf-8") as f:
                            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
                        logger.info("✓ Saved transcript.json with %d segments", len(transcript_data["segments"]))

                    except Exception as e:
                        logger.exception("CRITICAL: Transcription failed: %s", e)
                        # Save error to file for debugging
                        error_data = {"segments": [], "text": "", "error": str(e)}
                        with open(analysis_dir / "transcript_error.json", "w", encoding="utf-8") as f:
                            json.dump(error_data, f, indent=2)
                        # Re-raise to fail the job properly - no transcription = no segments
                        raise RuntimeError(f"Transcription failed: {e}") from e

            # ========================================
            # PARALLEL PROCESSING: Audio + Scene Detection
            # ========================================
            # These analyses are independent and can run in parallel
            # This provides ~20% speedup on analysis phase

            audio_progress_value = [0.0]
            scene_progress_value = [0.0]

            def update_parallel_progress():
                """Update job progress based on parallel analyses."""
                combined = (audio_progress_value[0] + scene_progress_value[0]) / 2
                job_manager.update_progress(
                    job,
                    40 + combined * 0.25,  # 40% to 65%
                    "parallel_analysis",
                    f"Audio: {audio_progress_value[0]:.0f}% | Scènes: {scene_progress_value[0]:.0f}%"
                )

            async def run_audio_analysis():
                nonlocal audio_data
                if not (analyze_audio and self.audio_analyzer):
                    audio_progress_value[0] = 100.0
                    if analyze_audio:
                        logger.warning("Audio analyzer not available, skipping")
                    return None

                cached = load_cached_step("audio_analysis.json")
                if cached:
                    audio_data = cached
                    audio_progress_value[0] = 100.0
                    logger.info("✓ Audio analysis loaded from cache")
                    return cached

                try:
                    def audio_progress(p):
                        audio_progress_value[0] = p
                        update_parallel_progress()

                    result = await self.audio_analyzer.analyze(
                        project.audio_path,
                        progress_callback=audio_progress
                    )

                    # Save audio analysis
                    with open(analysis_dir / "audio_analysis.json", "w") as f:
                        json.dump(result, f, indent=2)
                    logger.info("✓ Saved audio_analysis.json")
                    audio_data = result
                    return result

                except Exception as e:
                    logger.exception("Audio analysis failed: %s", e)
                    return {"error": str(e)}

            async def run_scene_detection():
                nonlocal scene_data
                if not (detect_scenes and self.scene_detector):
                    scene_progress_value[0] = 100.0
                    if detect_scenes:
                        logger.warning("Scene detector not available, skipping")
                    return None

                cached = load_cached_step("scenes.json")
                if cached:
                    scene_data = cached
                    scene_progress_value[0] = 100.0
                    logger.info("✓ Scene detection loaded from cache")
                    return cached

                video_path = project.proxy_path or project.source_path

                try:
                    def scene_progress(p):
                        scene_progress_value[0] = p
                        update_parallel_progress()

                    result = await self.scene_detector.detect_scenes(
                        video_path,
                        progress_callback=scene_progress
                    )

                    # Save scene data
                    with open(analysis_dir / "scenes.json", "w") as f:
                        json.dump(result, f, indent=2)
                    logger.info("✓ Saved scenes.json")
                    scene_data = result
                    return result

                except Exception as e:
                    logger.exception("Scene detection failed: %s", e)
                    return {"scenes": [], "error": str(e)}

            # Run both analyses in parallel
            job_manager.update_progress(job, 40, "parallel_analysis", "Analyses parallèles: Audio + Scènes...")
            logger.info("Starting PARALLEL analysis: Audio + Scene detection")

            parallel_results = await asyncio.gather(
                run_audio_analysis(),
                run_scene_detection(),
                return_exceptions=True
            )

            # Process results
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    logger.error("Parallel analysis task %d failed: %s", i, result)

            # Build timeline layers from results
            if audio_data and "error" not in audio_data:
                timeline_layers.append({
                    "id": "audio_energy",
                    "name": "Audio Energy",
                    "type": "audio_energy",
                    "data": audio_data.get("energy_timeline", []),
                    "color": "#FF6B6B"
                })

            if scene_data and "error" not in scene_data:
                timeline_layers.append({
                    "id": "scene_changes",
                    "name": "Scene Changes",
                    "type": "scene_changes",
                    "data": [{"time": s["time"], "value": s["confidence"]} for s in scene_data.get("scenes", [])],
                    "color": "#4ECDC4"
                })

            logger.info("PARALLEL analysis complete")

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

                # Twitch chat signal (chat-velocity / emote bursts). Best-effort:
                # cached, Twitch-only, and any failure leaves chat_data=None so a
                # chat outage can never fail the analysis.
                chat_data = None
                if settings.CHAT_SIGNAL:
                    try:
                        from forge_engine.services.twitch_chat import (
                            build_chat_intensity,
                            extract_video_id,
                            fetch_vod_chat,
                        )
                        chat_data = load_cached_step("chat_analysis.json")
                        meta = project.project_meta or {}
                        if not chat_data and "twitch" in str(meta.get("platform", "")).lower():
                            vid = extract_video_id(meta, meta.get("importUrl"))
                            if vid:
                                job_manager.update_progress(job, 86, "scoring", "Lecture du chat Twitch...")
                                msgs = await fetch_vod_chat(vid, duration=project.duration or None)
                                dur = project.duration or ((msgs[-1]["offset"] + 3) if msgs else 0)
                                chat_data = build_chat_intensity(msgs, dur)
                                with open(analysis_dir / "chat_analysis.json", "w") as f:
                                    json.dump(chat_data, f)
                                logger.info(
                                    "✓ Chat signal: %d msgs, %d spikes (peak z=%.1f)",
                                    chat_data.get("total_messages", 0),
                                    len(chat_data.get("spikes", [])),
                                    chat_data.get("peak_z", 0.0),
                                )
                    except Exception as e:
                        logger.warning("Chat signal failed (continuing without): %s", e)
                        chat_data = None

                # Generate candidate segments
                candidate_segments = self.virality.generate_segments(
                    transcript_data.get("segments", []),
                    project.duration or 0,
                    audio_data=audio_data,
                    scene_data=scene_data
                )

                # Score segments. Prefer the async path (heuristic + LLM merge on
                # the top ~50 candidates); it self-gates to heuristic-only when
                # the LLM is unavailable. Emotion blend stays off (deepface/fer
                # not installed in this venv).
                if settings.LLM_SCORING:
                    scored_segments = await self.virality.score_segments_async(
                        candidate_segments,
                        transcript_data=transcript_data,
                        audio_data=audio_data,
                        scene_data=scene_data,
                        chat_data=chat_data,
                        use_llm=True,
                        use_emotions=False,
                    )
                else:
                    scored_segments = self.virality.score_segments(
                        candidate_segments,
                        transcript_data=transcript_data,
                        audio_data=audio_data,
                        scene_data=scene_data,
                        chat_data=chat_data
                    )

                # Deduplicate overlapping segments
                final_segments = self.virality.deduplicate_segments(scored_segments, max_segments=500)

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

            # Broadcast project update via WebSocket
            from forge_engine.api.v1.endpoints.websockets import broadcast_project_update
            broadcast_project_update({
                "id": project.id,
                "status": project.status,
                "name": project.name,
                "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
            })

            job_manager.update_progress(job, 100, "complete", f"Analysis complete - {len(segments)} segments found")

            # Check for auto-export
            auto_exported = await self._check_auto_export(db, project_id, segments, job_manager)

            return {
                "project_id": project_id,
                "segments_count": len(segments),
                "timeline_layers": len(timeline_layers),
                "transcript_available": transcript_data is not None,
                "auto_exported": auto_exported,
            }

    async def _check_auto_export(
        self,
        db: AsyncSession,
        project_id: str,
        segments: list[Segment],
        job_manager: JobManager
    ) -> int:
        """Check if auto-export is configured and trigger exports for top segments."""
        try:
            from forge_engine.core.jobs import JobType
            from forge_engine.models.profile import ExportProfile
            from forge_engine.services.export import ExportService

            # Find default profile
            result = await db.execute(
                select(ExportProfile).where(ExportProfile.is_default)
            )
            profile = result.scalar_one_or_none()

            if not profile:
                logger.debug("No default profile - skipping auto-export")
                return 0

            segment_filters = profile.segment_filters or {}
            auto_count = segment_filters.get("auto_export_count", 0)

            if auto_count <= 0:
                logger.debug("Auto-export disabled in profile")
                return 0

            min_score = segment_filters.get("min_score", 50)
            min_duration = segment_filters.get("min_duration", 30)
            max_duration = segment_filters.get("max_duration", 180)

            # Filter segments matching criteria
            eligible = [
                s for s in segments
                if s.score_total >= min_score
                and min_duration <= s.duration <= max_duration
            ]

            # Sort by score and take top N
            eligible.sort(key=lambda s: s.score_total, reverse=True)
            top_segments = eligible[:auto_count]

            if not top_segments:
                logger.info("No segments meet auto-export criteria")
                return 0

            logger.info(f"Auto-exporting {len(top_segments)} segments (profile: {profile.name})")

            export_service = ExportService()

            for segment in top_segments:
                # Create export job with profile settings
                await job_manager.create_job(
                    job_type=JobType.EXPORT,
                    handler=export_service.run_export,
                    project_id=project_id,
                    segment_id=segment.id,
                    variant="A",
                    platform="tiktok",
                    include_captions=True,
                    burn_subtitles=profile.export_settings.get("burn_subtitles", True),
                    include_cover=profile.export_settings.get("include_cover", True),
                    include_metadata=True,
                    use_nvenc=profile.export_settings.get("use_nvenc", True),
                    caption_style=profile.subtitle_style,
                    layout_config=profile.layout_config,
                    intro_config=profile.intro_config if profile.intro_config.get("enabled") else None,
                    music_config=profile.music_config if profile.music_config.get("path") else None,
                )

            return len(top_segments)

        except Exception as e:
            logger.warning(f"Auto-export check failed: {e}")
            return 0

