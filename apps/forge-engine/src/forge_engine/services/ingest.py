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
        normalize_audio: bool = True
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
            
            job_manager.update_progress(job, 100, "complete", "Ingestion complete")
            
            return {
                "project_id": project_id,
                "proxy_path": project.proxy_path,
                "audio_path": project.audio_path,
                "video_info": video_info,
            }


