"""Channel monitoring endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.database import get_db
from forge_engine.models import WatchedChannel, DetectedVOD

router = APIRouter()


# Request/Response Models
class AddChannelRequest(BaseModel):
    channel_id: str
    channel_name: str
    platform: str  # twitch, youtube
    display_name: Optional[str] = None
    check_interval: int = 3600  # 1 hour default
    auto_import: bool = False
    enabled: bool = True


class UpdateChannelRequest(BaseModel):
    display_name: Optional[str] = None
    check_interval: Optional[int] = None
    auto_import: Optional[bool] = None
    enabled: Optional[bool] = None


class UpdateVODStatusRequest(BaseModel):
    status: str  # new, imported, ignored


# Endpoints
@router.get("")
async def list_channels(
    platform: Optional[str] = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List all watched channels."""
    query = select(WatchedChannel)
    
    if platform:
        query = query.where(WatchedChannel.platform == platform)
    if enabled_only:
        query = query.where(WatchedChannel.enabled == True)
    
    query = query.order_by(WatchedChannel.created_at.desc())
    
    result = await db.execute(query)
    channels = result.scalars().all()
    
    return {
        "success": True,
        "data": [c.to_dict() for c in channels]
    }


@router.post("")
async def add_channel(
    request: AddChannelRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Add a new channel to monitor."""
    # Check if already exists
    existing = await db.execute(
        select(WatchedChannel).where(
            WatchedChannel.channel_id == request.channel_id,
            WatchedChannel.platform == request.platform
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Channel already being monitored")
    
    channel = WatchedChannel(
        channel_id=request.channel_id,
        channel_name=request.channel_name,
        display_name=request.display_name,
        platform=request.platform,
        check_interval=request.check_interval,
        auto_import=request.auto_import,
        enabled=request.enabled,
    )
    
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    
    # Try to get channel info via scraper
    try:
        from forge_engine.services.playwright_scraper import PlaywrightScraper
        scraper = PlaywrightScraper.get_instance()
        
        if request.platform == "twitch":
            info = await scraper.get_twitch_channel_info(request.channel_id)
            if info:
                channel.display_name = info.display_name
                channel.profile_image_url = info.profile_image_url
                await db.commit()
    except Exception:
        pass  # Continue without additional info
    
    return {"success": True, "data": channel.to_dict()}


@router.get("/{channel_id}")
async def get_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a specific watched channel."""
    result = await db.execute(
        select(WatchedChannel).where(WatchedChannel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return {"success": True, "data": channel.to_dict()}


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: str,
    request: UpdateChannelRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update a watched channel's settings."""
    result = await db.execute(
        select(WatchedChannel).where(WatchedChannel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if request.display_name is not None:
        channel.display_name = request.display_name
    if request.check_interval is not None:
        channel.check_interval = request.check_interval
    if request.auto_import is not None:
        channel.auto_import = request.auto_import
    if request.enabled is not None:
        channel.enabled = request.enabled
    
    await db.commit()
    await db.refresh(channel)
    
    return {"success": True, "data": channel.to_dict()}


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Remove a channel from monitoring."""
    result = await db.execute(
        select(WatchedChannel).where(WatchedChannel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    await db.delete(channel)
    await db.commit()
    
    return {"success": True, "message": "Channel removed"}


@router.post("/{channel_id}/check")
async def check_channel_now(
    channel_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Manually trigger a check for new VODs."""
    result = await db.execute(
        select(WatchedChannel).where(WatchedChannel.id == channel_id)
    )
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    from forge_engine.services.playwright_scraper import PlaywrightScraper
    scraper = PlaywrightScraper.get_instance()
    
    # Get VODs
    if channel.platform == "twitch":
        vods = await scraper.get_twitch_vods(channel.channel_id, limit=10)
    elif channel.platform == "youtube":
        vods = await scraper.get_youtube_channel_videos(
            f"https://www.youtube.com/@{channel.channel_id}", limit=10
        )
    else:
        vods = []
    
    # Find new VODs
    known_ids = set(channel.last_vod_ids or [])
    new_vods = []
    
    for vod in vods:
        if vod.id not in known_ids:
            # Create DetectedVOD record
            detected = DetectedVOD(
                external_id=vod.id,
                title=vod.title,
                channel_id=channel.channel_id,
                channel_name=channel.channel_name,
                platform=channel.platform,
                url=vod.url,
                thumbnail_url=vod.thumbnail_url,
                duration=vod.duration,
                published_at=vod.published_at,
                view_count=vod.view_count,
                status="new",
            )
            db.add(detected)
            new_vods.append(detected)
    
    # Update channel state
    channel.last_check_at = datetime.utcnow()
    channel.last_vod_ids = [v.id for v in vods]
    
    await db.commit()
    
    return {
        "success": True,
        "data": {
            "channel": channel.to_dict(),
            "newVods": [v.to_dict() for v in new_vods],
            "totalVods": len(vods),
        }
    }


# VOD endpoints
@router.get("/vods/detected")
async def list_detected_vods(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List detected VODs."""
    query = select(DetectedVOD)
    
    if status:
        query = query.where(DetectedVOD.status == status)
    if platform:
        query = query.where(DetectedVOD.platform == platform)
    
    # Count
    count_query = select(func.count()).select_from(DetectedVOD)
    if status:
        count_query = count_query.where(DetectedVOD.status == status)
    if platform:
        count_query = count_query.where(DetectedVOD.platform == platform)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(DetectedVOD.detected_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    vods = result.scalars().all()
    
    return {
        "success": True,
        "data": {
            "items": [v.to_dict() for v in vods],
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    }


@router.patch("/vods/{vod_id}")
async def update_vod_status(
    vod_id: str,
    request: UpdateVODStatusRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update a detected VOD's status."""
    result = await db.execute(
        select(DetectedVOD).where(DetectedVOD.id == vod_id)
    )
    vod = result.scalar_one_or_none()
    
    if not vod:
        raise HTTPException(status_code=404, detail="VOD not found")
    
    if request.status not in ("new", "imported", "ignored"):
        raise HTTPException(status_code=400, detail="Invalid status")
    
    vod.status = request.status
    await db.commit()
    await db.refresh(vod)
    
    return {"success": True, "data": vod.to_dict()}


@router.post("/vods/{vod_id}/import")
async def import_detected_vod(
    vod_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Import a detected VOD as a project."""
    result = await db.execute(
        select(DetectedVOD).where(DetectedVOD.id == vod_id)
    )
    vod = result.scalar_one_or_none()
    
    if not vod:
        raise HTTPException(status_code=404, detail="VOD not found")
    
    if vod.status == "imported":
        raise HTTPException(status_code=400, detail="VOD already imported")
    
    # Import via YouTube-DL service
    from forge_engine.services.youtube_dl import YouTubeDLService
    from forge_engine.models import Project
    from forge_engine.core.jobs import JobManager, JobType
    from forge_engine.services.ingest import IngestService
    from forge_engine.core.database import async_session_maker
    from forge_engine.core.config import settings
    
    yt_service = YouTubeDLService.get_instance()
    job_manager = JobManager.get_instance()
    
    # Create project
    project = Project(
        name=vod.title,
        source_path="",
        source_filename=f"{vod.title}.mp4",
        status="downloading",
        project_meta={
            "importUrl": vod.url,
            "platform": vod.platform,
            "channel": vod.channel_name,
            "detectedVodId": vod.id,
        }
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    # Update VOD status
    vod.status = "imported"
    vod.project_id = project.id
    await db.commit()
    
    # Create download job
    async def download_handler(job, **kwargs):
        project_id = kwargs.get("project_id")
        url = kwargs.get("url")
        
        async with async_session_maker() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            proj = result.scalar_one_or_none()
            
            if not proj:
                raise ValueError(f"Project not found: {project_id}")
            
            yt = YouTubeDLService.get_instance()
            
            def progress_cb(pct, msg):
                job_manager.update_progress(job, pct * 0.9, "download", msg)
            
            project_dir = settings.LIBRARY_PATH / "projects" / project_id
            source_dir = project_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            
            downloaded_path = await yt.download_video(url, source_dir, "best", progress_cb)
            
            if not downloaded_path:
                proj.status = "error"
                proj.error_message = "Download failed"
                await session.commit()
                raise ValueError("Download failed")
            
            proj.source_path = str(downloaded_path)
            proj.source_filename = downloaded_path.name
            proj.status = "created"
            await session.commit()
            
            job_manager.update_progress(job, 100, "complete", "Download complete")
            
            # Auto-chain to ingest
            ingest_service = IngestService()
            await job_manager.create_job(
                job_type=JobType.INGEST,
                handler=ingest_service.run_ingest,
                project_id=project_id,
                auto_analyze=True,
            )
            
            return {"downloaded_path": str(downloaded_path)}
    
    job = await job_manager.create_job(
        job_type=JobType.INGEST,
        handler=download_handler,
        project_id=project.id,
        url=vod.url,
    )
    
    return {
        "success": True,
        "data": {
            "project": project.to_dict(),
            "jobId": job.id,
        }
    }

