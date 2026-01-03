"""Project endpoints."""

import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.database import get_db
from forge_engine.core.jobs import JobManager, JobType
from forge_engine.models import Project, Segment, Artifact
from forge_engine.services.ingest import IngestService
from forge_engine.services.analysis import AnalysisService
from forge_engine.services.export import ExportService

router = APIRouter()


# Request/Response Models
class CreateProjectRequest(BaseModel):
    name: str
    source_path: str
    profile_id: Optional[str] = None


class IngestRequest(BaseModel):
    create_proxy: bool = True
    extract_audio: bool = True
    audio_track: int = 0
    normalize_audio: bool = True
    auto_analyze: bool = True  # Automatically start analysis after ingest


class AnalyzeRequest(BaseModel):
    transcribe: bool = True
    whisper_model: str = "large-v3"
    language: Optional[str] = None
    detect_scenes: bool = True
    analyze_audio: bool = True
    detect_faces: bool = True
    score_segments: bool = True
    custom_dictionary: Optional[list[str]] = None


class CaptionStyleRequest(BaseModel):
    fontFamily: str = "Inter"
    fontSize: int = 48
    fontWeight: int = 700
    color: str = "#FFFFFF"
    backgroundColor: str = "transparent"
    outlineColor: str = "#000000"
    outlineWidth: int = 2
    position: str = "bottom"  # bottom, center, top
    positionY: Optional[int] = None  # Custom Y position (0-1920, overrides position)
    animation: str = "none"  # none, fade, pop, bounce, glow, wave
    highlightColor: str = "#FFD700"
    wordsPerLine: int = 6


class SourceCropRequest(BaseModel):
    x: float = 0
    y: float = 0
    width: float = 1
    height: float = 1


class LayoutZoneRequest(BaseModel):
    x: float  # % position on 9:16 canvas
    y: float
    width: float
    height: float
    sourceCrop: Optional[SourceCropRequest] = None


class LayoutConfigRequest(BaseModel):
    facecam: Optional[LayoutZoneRequest] = None
    content: Optional[LayoutZoneRequest] = None
    facecamRatio: float = 0.4


class IntroConfigRequest(BaseModel):
    enabled: bool = False
    duration: float = 2.0
    title: str = ""
    badgeText: str = ""
    backgroundBlur: int = 15
    titleFont: str = "Montserrat"
    titleSize: int = 72
    titleColor: str = "#FFFFFF"
    badgeColor: str = "#00FF88"
    animation: str = "fade"  # fade, slide, zoom, bounce


class ExportRequest(BaseModel):
    segment_id: str
    variant: str = "A"
    template_id: Optional[str] = None
    platform: str = "tiktok"
    include_captions: bool = True
    burn_subtitles: bool = True
    include_cover: bool = False  # Default: only video file
    include_metadata: bool = False  # Default: only video file
    include_post: bool = False  # Default: only video file
    use_nvenc: bool = True
    caption_style: Optional[CaptionStyleRequest] = None
    layout_config: Optional[LayoutConfigRequest] = None
    intro_config: Optional[IntroConfigRequest] = None


class GenerateVariantsRequest(BaseModel):
    variants: list[dict]
    render_proxy: bool = True


class ApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    message: Optional[str] = None


class ImportUrlRequest(BaseModel):
    url: str
    quality: str = "best"  # best, 1080, 720, 480
    auto_ingest: bool = True
    auto_analyze: bool = True


# Endpoints
@router.post("")
async def create_project(
    request: CreateProjectRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Create a new project."""
    # Validate source path
    if not os.path.exists(request.source_path):
        raise HTTPException(status_code=400, detail="Source file not found")
    
    # Create project
    project = Project(
        name=request.name,
        source_path=request.source_path,
        source_filename=os.path.basename(request.source_path),
        profile_id=request.profile_id,
        status="created",
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    return {"success": True, "data": project.to_dict()}


@router.post("/import-url")
async def import_from_url(
    request: ImportUrlRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Import a video from YouTube or Twitch URL."""
    from forge_engine.services.youtube_dl import YouTubeDLService
    
    yt_service = YouTubeDLService.get_instance()
    
    # Validate URL
    if not yt_service.is_valid_url(request.url):
        raise HTTPException(status_code=400, detail="URL non valide (YouTube ou Twitch requis)")
    
    # Get video info first
    info = await yt_service.get_video_info(request.url)
    if not info:
        raise HTTPException(status_code=400, detail="Impossible de récupérer les informations de la vidéo")
    
    # Create project with placeholder
    project = Project(
        name=info.title,
        source_path="",  # Will be updated after download
        source_filename=f"{info.title}.mp4",
        status="downloading",
        project_meta={
            "importUrl": request.url,
            "platform": info.platform,
            "channel": info.channel,
            "uploadDate": info.upload_date,
            "viewCount": info.view_count,
        }
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    # Create download job
    job_manager = JobManager.get_instance()
    
    async def download_handler(job, **kwargs):
        """Handle video download."""
        from forge_engine.api.v1.endpoints.websockets import broadcast_project_update
        
        project_id = kwargs.get("project_id")
        url = kwargs.get("url")
        quality = kwargs.get("quality", "best")
        auto_ingest = kwargs.get("auto_ingest", True)
        auto_analyze = kwargs.get("auto_analyze", True)
        
        async with async_session_maker() as session:
            result = await session.execute(select(Project).where(Project.id == project_id))
            proj = result.scalar_one_or_none()
            
            if not proj:
                raise ValueError(f"Project not found: {project_id}")
            
            yt = YouTubeDLService.get_instance()
            
            def progress_cb(pct, msg):
                job_manager.update_progress(job, pct * 0.9, "download", msg)
            
            # Download to project directory
            project_dir = settings.LIBRARY_PATH / "projects" / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            source_dir = project_dir / "source"
            source_dir.mkdir(parents=True, exist_ok=True)
            
            downloaded_path = await yt.download_video(url, source_dir, quality, progress_cb)
            
            if not downloaded_path:
                proj.status = "error"
                proj.error_message = "Échec du téléchargement"
                await session.commit()
                raise ValueError("Download failed")
            
            # Update project
            proj.source_path = str(downloaded_path)
            proj.source_filename = downloaded_path.name
            proj.status = "created"
            await session.commit()
            
            broadcast_project_update({
                "id": proj.id,
                "status": "created",
                "name": proj.name,
                "sourcePath": str(downloaded_path),
            })
            
            job_manager.update_progress(job, 100, "complete", "Téléchargement terminé")
            
            # Auto-chain to ingest if enabled
            if auto_ingest:
                ingest_service = IngestService()
                await job_manager.create_job(
                    job_type=JobType.INGEST,
                    handler=ingest_service.run_ingest,
                    project_id=project_id,
                    auto_analyze=auto_analyze,
                )
            
            return {"downloaded_path": str(downloaded_path)}
    
    # Create job
    from forge_engine.core.database import async_session_maker
    
    job = await job_manager.create_job(
        job_type=JobType.INGEST,  # Reuse ingest type for now
        handler=download_handler,
        project_id=project.id,
        url=request.url,
        quality=request.quality,
        auto_ingest=request.auto_ingest,
        auto_analyze=request.auto_analyze,
    )
    
    return {
        "success": True,
        "data": {
            "project": project.to_dict(),
            "jobId": job.id,
            "videoInfo": info.to_dict(),
        }
    }


@router.post("/url-info")
async def get_url_info(request: ImportUrlRequest) -> dict:
    """Get video info from URL without downloading."""
    from forge_engine.services.youtube_dl import YouTubeDLService
    
    yt_service = YouTubeDLService.get_instance()
    
    if not yt_service.is_valid_url(request.url):
        raise HTTPException(status_code=400, detail="URL non valide")
    
    info = await yt_service.get_video_info(request.url)
    if not info:
        raise HTTPException(status_code=400, detail="Impossible de récupérer les informations")
    
    return {"success": True, "data": info.to_dict()}


@router.get("")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List all projects with segment counts and average scores."""
    query = select(Project)
    
    if search:
        query = query.where(Project.name.ilike(f"%{search}%"))
    if status:
        query = query.where(Project.status == status)
    
    # Count total
    count_query = select(func.count()).select_from(Project)
    if search:
        count_query = count_query.where(Project.name.ilike(f"%{search}%"))
    if status:
        count_query = count_query.where(Project.status == status)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Project.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    # Enrich with segment stats
    enriched_items = []
    for p in projects:
        item = p.to_dict()
        
        # Get segment count and average score
        stats_query = select(
            func.count(Segment.id).label("count"),
            func.avg(Segment.score_total).label("avg_score")
        ).where(Segment.project_id == p.id)
        
        stats_result = await db.execute(stats_query)
        stats = stats_result.first()
        
        item["segmentsCount"] = stats.count if stats else 0
        item["averageScore"] = round(stats.avg_score, 1) if stats and stats.avg_score else 0
        
        enriched_items.append(item)
    
    return {
        "success": True,
        "data": {
            "items": enriched_items,
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": (page * page_size) < total,
        }
    }


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {"success": True, "data": project.to_dict()}


@router.post("/{project_id}/ingest")
async def ingest_project(
    project_id: str,
    request: IngestRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Start ingestion for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create ingest job
    job_manager = JobManager.get_instance()
    ingest_service = IngestService()
    
    job = await job_manager.create_job(
        job_type=JobType.INGEST,
        handler=ingest_service.run_ingest,
        project_id=project_id,
        create_proxy=request.create_proxy,
        extract_audio=request.extract_audio,
        audio_track=request.audio_track,
        normalize_audio=request.normalize_audio,
        auto_analyze=request.auto_analyze,  # Pass to service for chaining
    )
    
    # Update project status
    project.status = "ingesting"
    await db.commit()
    
    return {"success": True, "data": {"jobId": job.id}}


@router.post("/{project_id}/analyze")
async def analyze_project(
    project_id: str,
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Start analysis for a project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.status not in ("ingested", "analyzed", "ready"):
        raise HTTPException(status_code=400, detail="Project must be ingested first")
    
    # Create analysis job
    job_manager = JobManager.get_instance()
    analysis_service = AnalysisService()
    
    job = await job_manager.create_job(
        job_type=JobType.ANALYZE,
        handler=analysis_service.run_analysis,
        project_id=project_id,
        transcribe=request.transcribe,
        whisper_model=request.whisper_model,
        language=request.language,
        detect_scenes=request.detect_scenes,
        analyze_audio=request.analyze_audio,
        detect_faces=request.detect_faces,
        score_segments=request.score_segments,
        custom_dictionary=request.custom_dictionary,
    )
    
    # Update project status
    project.status = "analyzing"
    await db.commit()
    
    return {"success": True, "data": {"jobId": job.id}}


@router.get("/{project_id}/timeline")
async def get_timeline(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get timeline data for a project."""
    from forge_engine.core.config import settings
    import json
    
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Load timeline from analysis cache
    project_dir = settings.LIBRARY_PATH / "projects" / project_id
    timeline_path = project_dir / "analysis" / "timeline.json"
    
    if not timeline_path.exists():
        return {
            "success": True,
            "data": {
                "projectId": project_id,
                "duration": project.duration or 0,
                "layers": [],
                "segments": [],
            }
        }
    
    with open(timeline_path, "r") as f:
        timeline_data = json.load(f)
    
    # Inject layout data if available
    layout_path = project_dir / "analysis" / "layout.json"
    if layout_path.exists():
        try:
            with open(layout_path, "r") as f:
                layout_data = json.load(f)
                timeline_data["faceDetections"] = layout_data.get("face_detections", [])
        except Exception:
            pass
    
    return {"success": True, "data": timeline_data}


@router.get("/{project_id}/segments")
async def list_segments(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("score", regex="^(score|startTime|duration)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List segments for a project."""
    query = select(Segment).where(Segment.project_id == project_id)
    
    if min_score is not None:
        query = query.where(Segment.score_total >= min_score)
    
    # Sorting
    sort_column = {
        "score": Segment.score_total,
        "startTime": Segment.start_time,
        "duration": Segment.duration,
    }[sort_by]
    
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Count
    count_query = select(func.count()).select_from(Segment).where(Segment.project_id == project_id)
    if min_score is not None:
        count_query = count_query.where(Segment.score_total >= min_score)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    segments = result.scalars().all()
    
    return {
        "success": True,
        "data": {
            "items": [s.to_dict() for s in segments],
            "total": total,
            "page": page,
            "pageSize": page_size,
            "hasMore": (page * page_size) < total,
        }
    }


@router.get("/{project_id}/segments/{segment_id}")
async def get_segment(
    project_id: str,
    segment_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a segment by ID."""
    result = await db.execute(
        select(Segment)
        .where(Segment.id == segment_id)
        .where(Segment.project_id == project_id)
    )
    segment = result.scalar_one_or_none()
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return {"success": True, "data": segment.to_dict()}


@router.post("/{project_id}/segments/{segment_id}/variants")
async def generate_variants(
    project_id: str,
    segment_id: str,
    request: GenerateVariantsRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Generate variants for a segment."""
    result = await db.execute(
        select(Segment)
        .where(Segment.id == segment_id)
        .where(Segment.project_id == project_id)
    )
    segment = result.scalar_one_or_none()
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    # Create variants job
    job_manager = JobManager.get_instance()
    export_service = ExportService()
    
    job = await job_manager.create_job(
        job_type=JobType.GENERATE_VARIANTS,
        handler=export_service.generate_variants,
        project_id=project_id,
        segment_id=segment_id,
        variants=request.variants,
        render_proxy=request.render_proxy,
    )
    
    return {"success": True, "data": {"jobId": job.id}}


@router.post("/{project_id}/export")
async def export_segment(
    project_id: str,
    request: ExportRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Export a segment."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    result = await db.execute(
        select(Segment)
        .where(Segment.id == request.segment_id)
        .where(Segment.project_id == project_id)
    )
    segment = result.scalar_one_or_none()
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    # Create export job
    job_manager = JobManager.get_instance()
    export_service = ExportService()
    
    job = await job_manager.create_job(
        job_type=JobType.EXPORT,
        handler=export_service.run_export,
        project_id=project_id,
        segment_id=request.segment_id,
        variant=request.variant,
        template_id=request.template_id,
        platform=request.platform,
        include_captions=request.include_captions,
        burn_subtitles=request.burn_subtitles,
        include_cover=request.include_cover,
        include_metadata=request.include_metadata,
        include_post=request.include_post,
        use_nvenc=request.use_nvenc,
        caption_style=request.caption_style.model_dump() if request.caption_style else None,
        layout_config=request.layout_config.model_dump() if request.layout_config else None,
        intro_config=request.intro_config.model_dump() if request.intro_config else None,
    )
    
    return {"success": True, "data": {"jobId": job.id}}


@router.get("/{project_id}/artifacts")
async def list_artifacts(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List all artifacts for a project."""
    result = await db.execute(
        select(Artifact)
        .where(Artifact.project_id == project_id)
        .order_by(Artifact.created_at.desc())
    )
    artifacts = result.scalars().all()
    
    return {"success": True, "data": [a.to_dict() for a in artifacts]}






