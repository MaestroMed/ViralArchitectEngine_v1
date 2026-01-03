"""Ingestion service for video processing."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.config import settings
from forge_engine.core.database import async_session_maker
from forge_engine.core.jobs import Job, JobManager
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
        project_id: Optional[str] = None,
        create_proxy: bool = True,
        extract_audio: bool = True,
        audio_track: int = 0,
        normalize_audio: bool = True,
        auto_analyze: bool = True
    ) -> Dict[str, Any]:
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
            
            source_path = project.source_path
            
            if not os.path.exists(source_path):
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
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
            
            # Create proxy
            if create_proxy:
                job_manager.update_progress(job, 15, "proxy", "Creating preview proxy...")
                
                proxy_path = proxy_dir / "proxy.mp4"
                
                def proxy_progress(p):
                    job_manager.update_progress(job, 15 + p * 0.4, "proxy", f"Creating proxy: {p:.0f}%")
                
                success = await self.ffmpeg.create_proxy(
                    source_path,
                    str(proxy_path),
                    width=settings.PROXY_WIDTH,
                    height=settings.PROXY_HEIGHT,
                    crf=settings.PROXY_CRF,
                    progress_callback=proxy_progress
                )
                
                if success:
                    project.proxy_path = str(proxy_path)
                    await db.commit()
                else:
                    logger.warning("Proxy creation failed, continuing without proxy")
            
            # Extract audio
            if extract_audio:
                job_manager.update_progress(job, 60, "audio", "Extracting audio...")
                
                audio_path = analysis_dir / "audio.wav"
                
                def audio_progress(p):
                    job_manager.update_progress(job, 60 + p * 0.35, "audio", f"Extracting audio: {p:.0f}%")
                
                success = await self.ffmpeg.extract_audio(
                    source_path,
                    str(audio_path),
                    sample_rate=settings.AUDIO_SAMPLE_RATE,
                    channels=1,
                    audio_track=audio_track,
                    normalize=normalize_audio,
                    progress_callback=audio_progress
                )
                
                if success:
                    project.audio_path = str(audio_path)
                    await db.commit()
                else:
                    logger.warning("Audio extraction failed, some features may be limited")
            
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
                from forge_engine.services.analysis import AnalysisService
                from forge_engine.core.jobs import JobType
                
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
                )
                logger.info("Analysis job created for project %s", project_id)
            
            return {
                "project_id": project_id,
                "proxy_path": project.proxy_path,
                "audio_path": project.audio_path,
                "video_info": video_info,
                "auto_analyze": auto_analyze,
            }


