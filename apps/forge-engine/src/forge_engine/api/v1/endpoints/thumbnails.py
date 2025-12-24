"""Thumbnail generation endpoints."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from forge_engine.core.config import settings
from forge_engine.services.ffmpeg import FFmpegService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/projects/{project_id}/thumbnail")
async def get_project_thumbnail(
    project_id: str,
    time: Optional[float] = Query(None, description="Time in seconds to extract frame"),
    width: int = Query(320, description="Thumbnail width"),
    height: int = Query(180, description="Thumbnail height"),
):
    """Generate or return a cached thumbnail for a project."""
    project_dir = settings.LIBRARY_PATH / "projects" / project_id
    
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Find video file
    proxy_path = project_dir / "proxy.mp4"
    if not proxy_path.exists():
        # Try to find any video in the directory
        videos = list(project_dir.glob("*.mp4")) + list(project_dir.glob("*.mov"))
        if not videos:
            raise HTTPException(status_code=404, detail="No video file found")
        proxy_path = videos[0]
    
    # Determine cache path
    time_str = f"_{int(time * 1000)}" if time else "_0"
    cache_name = f"thumb{time_str}_{width}x{height}.jpg"
    cache_path = project_dir / "thumbnails" / cache_name
    
    # Return cached if exists
    if cache_path.exists():
        return FileResponse(cache_path, media_type="image/jpeg")
    
    # Generate thumbnail
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    ffmpeg = FFmpegService()
    if not await ffmpeg.check_availability():
        raise HTTPException(status_code=500, detail="FFmpeg not available")
    
    try:
        await ffmpeg.extract_frame(
            str(proxy_path),
            str(cache_path),
            time=time or 1.0,  # Default to 1 second in
            width=width,
            height=height,
        )
        
        if not cache_path.exists():
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail")
        
        return FileResponse(cache_path, media_type="image/jpeg")
    
    except Exception as e:
        logger.exception("Thumbnail generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/segments/{segment_id}/thumbnail")
async def get_segment_thumbnail(
    project_id: str,
    segment_id: str,
    offset: float = Query(0.5, description="Offset ratio within segment (0-1)"),
    width: int = Query(320, description="Thumbnail width"),
    height: int = Query(180, description="Thumbnail height"),
):
    """Generate thumbnail for a specific segment."""
    from sqlalchemy import select
    from forge_engine.core.database import async_session_maker
    from forge_engine.models import Segment
    
    # Get segment timing
    async with async_session_maker() as db:
        result = await db.execute(
            select(Segment).where(
                Segment.id == segment_id,
                Segment.project_id == project_id
            )
        )
        segment = result.scalar_one_or_none()
        
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")
        
        # Calculate time within segment
        time = segment.start_time + (segment.duration * offset)
    
    # Use project thumbnail endpoint with calculated time
    return await get_project_thumbnail(project_id, time=time, width=width, height=height)


@router.post("/projects/{project_id}/thumbnails/batch")
async def generate_batch_thumbnails(
    project_id: str,
    interval: float = Query(10.0, description="Interval between thumbnails in seconds"),
    width: int = Query(160, description="Thumbnail width"),
    height: int = Query(90, description="Thumbnail height"),
):
    """Generate thumbnails at regular intervals for the whole video."""
    from sqlalchemy import select
    from forge_engine.core.database import async_session_maker
    from forge_engine.models import Project
    
    async with async_session_maker() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        duration = project.duration or 0
    
    if duration <= 0:
        raise HTTPException(status_code=400, detail="Project has no duration")
    
    project_dir = settings.LIBRARY_PATH / "projects" / project_id
    proxy_path = project_dir / "proxy.mp4"
    
    if not proxy_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    ffmpeg = FFmpegService()
    if not await ffmpeg.check_availability():
        raise HTTPException(status_code=500, detail="FFmpeg not available")
    
    # Generate thumbnails
    thumbnails_dir = project_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    
    generated = []
    current_time = 0.0
    
    while current_time < duration:
        cache_name = f"frame_{int(current_time * 1000)}_{width}x{height}.jpg"
        cache_path = thumbnails_dir / cache_name
        
        if not cache_path.exists():
            try:
                await ffmpeg.extract_frame(
                    str(proxy_path),
                    str(cache_path),
                    time=current_time,
                    width=width,
                    height=height,
                )
            except Exception as e:
                logger.warning("Failed to extract frame at %.1fs: %s", current_time, e)
        
        if cache_path.exists():
            generated.append({
                "time": current_time,
                "path": f"/thumbnails/{cache_name}",
                "url": f"/v1/projects/{project_id}/thumbnail?time={current_time}&width={width}&height={height}",
            })
        
        current_time += interval
    
    return {
        "project_id": project_id,
        "count": len(generated),
        "interval": interval,
        "thumbnails": generated,
    }





