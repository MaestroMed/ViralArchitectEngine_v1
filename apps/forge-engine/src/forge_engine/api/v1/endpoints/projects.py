"""Project endpoints."""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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


class AnalyzeRequest(BaseModel):
    transcribe: bool = True
    whisper_model: str = "large-v3"
    language: Optional[str] = None
    detect_scenes: bool = True
    analyze_audio: bool = True
    detect_faces: bool = True
    score_segments: bool = True
    custom_dictionary: Optional[list[str]] = None


class ExportRequest(BaseModel):
    segment_id: str
    variant: str = "A"
    template_id: Optional[str] = None
    platform: str = "tiktok"
    include_captions: bool = True
    include_cover: bool = True
    include_metadata: bool = True
    include_post: bool = True
    use_nvenc: bool = True


class GenerateVariantsRequest(BaseModel):
    variants: list[dict]
    render_proxy: bool = True


class ApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    message: Optional[str] = None


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


@router.get("")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List all projects."""
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
    
    return {
        "success": True,
        "data": {
            "items": [p.to_dict() for p in projects],
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
        include_cover=request.include_cover,
        include_metadata=request.include_metadata,
        include_post=request.include_post,
        use_nvenc=request.use_nvenc,
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






