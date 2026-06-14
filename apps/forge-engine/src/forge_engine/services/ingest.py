"""Ingestion service for video processing."""

import asyncio
import logging
from typing import Any

from sqlalchemy import select

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import Job, JobManager
from forge_engine.core.security import SourcePathError, validate_source_path
from forge_engine.models import Project
from forge_engine.services.ffmpeg import FFmpegService

logger = logging.getLogger(__name__)


class IngestService:
    """Service for ingesting and preparing video files."""

    def __init__(self):
        self.ffmpeg = FFmpegService()

    async def run_ingest(
        self,
        job: Job,
        project_id: str | None = None,
        create_proxy: bool = True,
        extract_audio: bool = True,
        audio_track: int = 0,
        normalize_audio: bool = True,
        auto_analyze: bool = True,
        dictionary_name: str | None = None
    ) -> dict[str, Any]:
        """Run the ingestion pipeline."""
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

            # Re-validate the stored source_path at ingest time: the DB row may
            # predate validation, and symlinks/mounts can change between project
            # creation and ingest. Downloaded sources live under LIBRARY_PATH,
            # which is an allowed root, so URL imports still pass.
            try:
                source_path = str(validate_source_path(project.source_path))
            except SourcePathError as exc:
                project.status = "error"
                project.error_message = f"Invalid source_path: {exc}"
                await db.commit()
                raise FileNotFoundError(str(exc)) from exc

            # Create project directory structure
            project_dir = settings.LIBRARY_PATH / "projects" / project_id
            source_dir = project_dir / "source"
            proxy_dir = project_dir / "proxy"
            analysis_dir = project_dir / "analysis"
            renders_dir = project_dir / "renders"
            exports_dir = project_dir / "exports"

            for d in [source_dir, proxy_dir, analysis_dir, renders_dir, exports_dir]:
                d.mkdir(parents=True, exist_ok=True)

            # Update progress
            job_manager.update_progress(job, 5, "probe", "Analyzing source file...")

            # Probe source file
            try:
                video_info = await self.ffmpeg.get_video_info(source_path)
            except Exception as e:
                project.status = "error"
                project.error_message = f"Failed to probe video: {e}"
                await db.commit()
                raise

            # Update project with video info
            project.width = video_info["width"]
            project.height = video_info["height"]
            project.duration = video_info["duration"]
            project.fps = video_info["fps"]
            project.audio_tracks = video_info["audio_tracks"]

            await db.commit()

            job_manager.update_progress(job, 10, "probe", f"Video: {video_info['width']}x{video_info['height']}, {video_info['duration']:.1f}s")

            # Extract thumbnail
            job_manager.update_progress(job, 12, "thumbnail", "Extracting thumbnail...")
            thumbnail_path = project_dir / "thumbnail.jpg"

            try:
                success = await self.ffmpeg.extract_thumbnail(
                    source_path,
                    str(thumbnail_path),
                    time_percent=0.1,  # 10% into the video
                    width=640,
                    height=360
                )
                if success:
                    project.thumbnail_path = str(thumbnail_path)
                    await db.commit()
                    logger.info("Thumbnail extracted: %s", thumbnail_path)
                else:
                    logger.warning("Thumbnail extraction failed, continuing without thumbnail")
            except Exception as e:
                logger.warning("Thumbnail extraction error: %s", e)

            # ========================================
            # PARALLEL PROCESSING: Proxy + Audio
            # ========================================
            # These operations are independent and can run in parallel
            # This provides ~35% speedup on ingestion

            proxy_path = proxy_dir / "proxy.mp4"
            audio_path = analysis_dir / "audio.wav"

            # Track individual progress for combined display
            proxy_progress_value = [0.0]
            audio_progress_value = [0.0]

            def update_combined_progress():
                """Update job progress based on both tasks."""
                # Proxy: 15-55% (40% range), Audio: 15-95% (35% range, faster)
                # Combined: 15-95% based on average
                combined = (proxy_progress_value[0] + audio_progress_value[0]) / 2
                job_manager.update_progress(
                    job,
                    15 + combined * 0.8,  # 15% to 95%
                    "parallel",
                    f"Proxy: {proxy_progress_value[0]:.0f}% | Audio: {audio_progress_value[0]:.0f}%"
                )

            def proxy_progress(p):
                proxy_progress_value[0] = p
                update_combined_progress()

            def audio_progress(p):
                audio_progress_value[0] = p
                update_combined_progress()

            # Check if we should skip proxy (NVENC available = fast final render)
            if settings.SKIP_PROXY_IF_NVENC and self.ffmpeg.has_nvenc:
                create_proxy = False
                logger.info("Skipping proxy creation (NVENC available for fast final render)")

            job_manager.update_progress(job, 15, "parallel", "Traitement parallèle: Proxy + Audio...")
            logger.info("Starting PARALLEL processing: Proxy=%s, Audio=%s", create_proxy, extract_audio)

            # Create tasks for parallel execution
            proxy_result = [False]
            audio_result = [False]

            async def run_proxy():
                if create_proxy:
                    result = await self.ffmpeg.create_proxy(
                        source_path,
                        str(proxy_path),
                        width=settings.PROXY_WIDTH,
                        height=settings.PROXY_HEIGHT,
                        crf=settings.PROXY_CRF,
                        progress_callback=proxy_progress
                    )
                    proxy_result[0] = result
                    return result
                # No proxy needed, mark as complete
                proxy_progress_value[0] = 100.0
                return True

            async def run_audio():
                if extract_audio:
                    result = await self.ffmpeg.extract_audio(
                        source_path,
                        str(audio_path),
                        sample_rate=settings.AUDIO_SAMPLE_RATE,
                        channels=1,
                        audio_track=audio_track,
                        normalize=normalize_audio,
                        progress_callback=audio_progress
                    )
                    audio_result[0] = result
                    return result
                return True

            # Run both tasks in parallel
            results = await asyncio.gather(run_proxy(), run_audio(), return_exceptions=True)

            # Handle results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error("Parallel task %d failed: %s", i, result)

            # Update project with results
            if create_proxy and proxy_result[0]:
                project.proxy_path = str(proxy_path)
                logger.info("Proxy created successfully")
            elif create_proxy:
                logger.warning("Proxy creation failed, continuing without proxy")

            if extract_audio and audio_result[0]:
                project.audio_path = str(audio_path)
                logger.info("Audio extracted successfully")
            elif extract_audio:
                logger.warning("Audio extraction failed, some features may be limited")

            await db.commit()
            logger.info("PARALLEL processing complete")

            # Update project status
            project.status = "ingested"
            await db.commit()

            # Broadcast project update via WebSocket
            from forge_engine.api.v1.endpoints.websockets import broadcast_project_update
            broadcast_project_update({
                "id": project.id,
                "status": project.status,
                "name": project.name,
                "width": project.width,
                "height": project.height,
                "duration": project.duration,
                "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
            })

            job_manager.update_progress(job, 100, "complete", "Ingestion complete")

            # Auto-chain to analysis if enabled
            if auto_analyze:
                logger.info("Auto-chaining to analysis for project %s", project_id)
                from forge_engine.core.jobs import JobType
                from forge_engine.services.analysis import AnalysisService

                analysis_service = AnalysisService()

                # Update project status
                project.status = "analyzing"
                await db.commit()

                broadcast_project_update({
                    "id": project.id,
                    "status": "analyzing",
                    "name": project.name,
                })

                # Create analysis job
                await job_manager.create_job(
                    job_type=JobType.ANALYZE,
                    handler=analysis_service.run_analysis,
                    project_id=project_id,
                    transcribe=True,
                    whisper_model="large-v3",
                    language=None,
                    detect_scenes=True,
                    analyze_audio=True,
                    detect_faces=True,
                    score_segments=True,
                    dictionary_name=dictionary_name,
                )
                logger.info("Analysis job created for project %s (dictionary: %s)", project_id, dictionary_name or "none")

            return {
                "project_id": project_id,
                "proxy_path": project.proxy_path,
                "audio_path": project.audio_path,
                "video_info": video_info,
                "auto_analyze": auto_analyze,
            }


