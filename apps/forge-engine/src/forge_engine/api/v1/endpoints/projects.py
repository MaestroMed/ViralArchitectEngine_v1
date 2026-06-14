"""Project endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.database import get_db

logger = logging.getLogger(__name__)
from forge_engine.core.jobs import JobManager, JobType
from forge_engine.core.security import SourcePathError, validate_source_path
from forge_engine.models import Artifact, Project, Segment
from forge_engine.services.analysis import AnalysisService
from forge_engine.services.export import ExportService
from forge_engine.services.ingest import IngestService

router = APIRouter()


# Request/Response Models
class CreateProjectRequest(BaseModel):
    name: str
    source_path: str
    profile_id: str | None = None


class IngestRequest(BaseModel):
    create_proxy: bool = True
    extract_audio: bool = True
    audio_track: int = 0
    normalize_audio: bool = True
    auto_analyze: bool = True  # Automatically start analysis after ingest


class AnalyzeRequest(BaseModel):
    transcribe: bool = True
    whisper_model: str = "large-v3"
    language: str | None = None
    detect_scenes: bool = True
    analyze_audio: bool = True
    detect_faces: bool = True
    score_segments: bool = True
    custom_dictionary: list[str] | None = None
    dictionary_name: str | None = None  # Named dictionary (e.g. "etostark")


class CaptionStyleRequest(BaseModel):
    fontFamily: str = "Inter"
    fontSize: int = 48
    fontWeight: int = 700
    color: str = "#FFFFFF"
    backgroundColor: str = "transparent"
    outlineColor: str = "#000000"
    outlineWidth: int = 2
    position: str = "bottom"  # bottom, center, top
    positionY: int | None = None  # Custom Y position (0-1920, overrides position)
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
    sourceCrop: SourceCropRequest | None = None


class LayoutConfigRequest(BaseModel):
    facecam: LayoutZoneRequest | None = None
    content: LayoutZoneRequest | None = None
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


class MusicConfigRequest(BaseModel):
    path: str  # Path to MP3 file
    volume: float = 0.5  # 0.0 to 1.0
    startOffset: float = 0.0  # Seconds to skip at start of music


class JumpCutConfigRequest(BaseModel):
    enabled: bool = False
    sensitivity: str = "normal"  # "light", "normal", "aggressive"
    min_silence_ms: int | None = None  # Override: minimum silence to cut (ms)
    padding_ms: int = 50  # Padding to keep before/after speech
    transition: str = "hard"  # "hard", "zoom", "crossfade"


class ExportRequest(BaseModel):
    segment_id: str
    variant: str = "A"
    template_id: str | None = None
    platform: str = "tiktok"
    include_captions: bool = True
    burn_subtitles: bool = True
    include_cover: bool = False  # Default: only video file
    include_metadata: bool = False  # Default: only video file
    include_post: bool = False  # Default: only video file
    use_nvenc: bool = True
    caption_style: CaptionStyleRequest | None = None
    layout_config: LayoutConfigRequest | None = None
    intro_config: IntroConfigRequest | None = None
    music_config: MusicConfigRequest | None = None
    jump_cut_config: JumpCutConfigRequest | None = None


class GenerateVariantsRequest(BaseModel):
    variants: list[dict]
    render_proxy: bool = True


class ApiResponse(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None
    message: str | None = None


class ImportUrlRequest(BaseModel):
    url: str
    quality: str = "best"  # best, 1080, 720, 480
    auto_ingest: bool = True
    auto_analyze: bool = True
    dictionary_name: str | None = None  # Named dictionary (e.g. "etostark")


# Endpoints
@router.post("")
async def create_project(
    request: CreateProjectRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Create a new project."""
    # Validate source path: resolve symlinks, reject control chars / traversal,
    # and enforce the import-root allowlist (prevents path-traversal + symlink
    # escape through the public API surface).
    try:
        resolved_source = validate_source_path(request.source_path)
    except SourcePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Create project
    project = Project(
        name=request.name,
        source_path=str(resolved_source),
        source_filename=resolved_source.name,
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
        from forge_engine.core.config import settings
        from forge_engine.core.database import async_session_maker

        project_id = kwargs.get("project_id")
        url = kwargs.get("url")
        quality = kwargs.get("quality", "best")
        auto_ingest = kwargs.get("auto_ingest", True)
        auto_analyze = kwargs.get("auto_analyze", True)
        dictionary_name = kwargs.get("dictionary_name")

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
                    dictionary_name=dictionary_name,
                )

            return {"downloaded_path": str(downloaded_path)}

    # Create job
    job = await job_manager.create_job(
        job_type=JobType.DOWNLOAD,
        handler=download_handler,
        project_id=project.id,
        url=request.url,
        quality=request.quality,
        auto_ingest=request.auto_ingest,
        auto_analyze=request.auto_analyze,
        dictionary_name=request.dictionary_name,
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
    search: str | None = None,
    status: str | None = None,
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

    # Batch-fetch segment stats for all projects in one query (avoids N+1)
    project_ids = [p.id for p in projects]
    stats_map: dict[str, dict] = {}
    if project_ids:
        stats_query = (
            select(
                Segment.project_id,
                func.count(Segment.id).label("count"),
                func.avg(Segment.score_total).label("avg_score"),
            )
            .where(Segment.project_id.in_(project_ids))
            .group_by(Segment.project_id)
        )
        stats_result = await db.execute(stats_query)
        for row in stats_result.all():
            stats_map[row.project_id] = {
                "count": row.count,
                "avg_score": row.avg_score,
            }

    enriched_items = []
    for p in projects:
        item = p.to_dict()
        stats = stats_map.get(p.id)
        item["segmentsCount"] = stats["count"] if stats else 0
        item["averageScore"] = round(stats["avg_score"], 1) if stats and stats["avg_score"] else 0
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


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete a project and all its associated data."""
    import shutil

    from forge_engine.core.config import settings

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_name = project.name

    # Delete associated segments
    await db.execute(
        Segment.__table__.delete().where(Segment.project_id == project_id)
    )

    # Delete associated artifacts
    await db.execute(
        Artifact.__table__.delete().where(Artifact.project_id == project_id)
    )

    # Delete the project record
    await db.delete(project)
    await db.commit()

    # Delete project folder from disk
    project_dir = settings.LIBRARY_PATH / "projects" / project_id
    if project_dir.exists():
        try:
            shutil.rmtree(project_dir)
            logger.info(f"Deleted project folder: {project_dir}")
        except Exception as e:
            logger.warning(f"Could not delete project folder: {e}")

    logger.info(f"Deleted project: {project_name} ({project_id})")

    return {"success": True, "message": f"Projet '{project_name}' supprimé"}


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
        dictionary_name=request.dictionary_name,
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
    import json

    from forge_engine.core.config import settings

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

    with open(timeline_path) as f:
        timeline_data = json.load(f)

    # Inject layout data if available
    layout_path = project_dir / "analysis" / "layout.json"
    if layout_path.exists():
        try:
            with open(layout_path) as f:
                layout_data = json.load(f)
                timeline_data["faceDetections"] = layout_data.get("face_detections", [])
        except Exception:
            pass

    return {"success": True, "data": timeline_data}


@router.get("/{project_id}/segments")
async def list_segments(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    sort_by: str = Query("score", regex="^(score|startTime|duration)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    min_score: float | None = Query(None, ge=0, le=100),
    min_duration: float | None = Query(None, ge=0),
    max_duration: float | None = Query(None, ge=0),
    search: str | None = Query(None, min_length=1, max_length=200),
    tags: str | None = Query(None),  # Comma-separated tags
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List segments for a project with advanced filtering and search."""
    query = select(Segment).where(Segment.project_id == project_id)

    # Apply filters
    if min_score is not None:
        query = query.where(Segment.score_total >= min_score)
    if min_duration is not None:
        query = query.where(Segment.duration >= min_duration)
    if max_duration is not None:
        query = query.where(Segment.duration <= max_duration)

    # Full-text search on transcript
    if search:
        search_term = f"%{search.lower()}%"
        query = query.where(
            Segment.transcript.ilike(search_term) |
            Segment.topic_label.ilike(search_term) |
            Segment.hook_text.ilike(search_term)
        )

    # Tag filtering (check if any of the requested tags are in score_tags JSON array)
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        if tag_list:
            # SQLite JSON array contains check
            from sqlalchemy import or_
            tag_conditions = []
            for tag in tag_list:
                # Use JSON contains for SQLite
                tag_conditions.append(
                    Segment.score_tags.contains(tag)
                )
            if tag_conditions:
                query = query.where(or_(*tag_conditions))

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

    # Count with same filters
    count_query = select(func.count()).select_from(Segment).where(Segment.project_id == project_id)
    if min_score is not None:
        count_query = count_query.where(Segment.score_total >= min_score)
    if min_duration is not None:
        count_query = count_query.where(Segment.duration >= min_duration)
    if max_duration is not None:
        count_query = count_query.where(Segment.duration <= max_duration)
    if search:
        search_term = f"%{search.lower()}%"
        count_query = count_query.where(
            Segment.transcript.ilike(search_term) |
            Segment.topic_label.ilike(search_term) |
            Segment.hook_text.ilike(search_term)
        )

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


@router.get("/{project_id}/segments/tags")
async def get_segment_tags(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get all unique tags used in segments for a project."""
    result = await db.execute(
        select(Segment.score_tags).where(Segment.project_id == project_id)
    )
    all_tags_lists = result.scalars().all()

    # Flatten and deduplicate tags
    unique_tags = set()
    for tags_list in all_tags_lists:
        if tags_list:
            for tag in tags_list:
                if tag:
                    unique_tags.add(tag.lower())

    # Sort alphabetically
    sorted_tags = sorted(unique_tags)

    return {
        "success": True,
        "data": {
            "tags": sorted_tags,
            "count": len(sorted_tags),
        }
    }


@router.get("/{project_id}/segments/stats")
async def get_segment_stats(
    project_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get segment statistics for a project including score distribution."""
    # Get all segments for this project
    result = await db.execute(
        select(Segment).where(Segment.project_id == project_id)
    )
    segments = result.scalars().all()

    if not segments:
        return {
            "success": True,
            "data": {
                "total": 0,
                "avgScore": 0,
                "maxScore": 0,
                "minScore": 0,
                "avgDuration": 0,
                "maxDuration": 0,
                "minDuration": 0,
                "scoreDistribution": [0, 0, 0, 0, 0],
                "durationDistribution": [0, 0, 0, 0, 0],
                "monetizable": 0,
                "highScore": 0,
            }
        }

    scores = [s.score_total or 0 for s in segments]
    durations = [s.duration or 0 for s in segments]

    # Score distribution: 0-20, 20-40, 40-60, 60-80, 80-100
    score_buckets = [0, 0, 0, 0, 0]
    for score in scores:
        if score < 20:
            score_buckets[0] += 1
        elif score < 40:
            score_buckets[1] += 1
        elif score < 60:
            score_buckets[2] += 1
        elif score < 80:
            score_buckets[3] += 1
        else:
            score_buckets[4] += 1

    # Duration distribution: 0-30s, 30-60s, 60-120s, 120-300s, 300s+
    duration_buckets = [0, 0, 0, 0, 0]
    for dur in durations:
        if dur < 30:
            duration_buckets[0] += 1
        elif dur < 60:
            duration_buckets[1] += 1
        elif dur < 120:
            duration_buckets[2] += 1
        elif dur < 300:
            duration_buckets[3] += 1
        else:
            duration_buckets[4] += 1

    return {
        "success": True,
        "data": {
            "total": len(segments),
            "avgScore": round(sum(scores) / len(scores), 1) if scores else 0,
            "maxScore": max(scores) if scores else 0,
            "minScore": min(scores) if scores else 0,
            "avgDuration": round(sum(durations) / len(durations), 1) if durations else 0,
            "maxDuration": max(durations) if durations else 0,
            "minDuration": min(durations) if durations else 0,
            "scoreDistribution": score_buckets,
            "durationDistribution": duration_buckets,
            "monetizable": len([d for d in durations if d >= 60]),
            "highScore": len([s for s in scores if s >= 60]),
        }
    }


@router.get("/{project_id}/segments/suggestions")
async def get_segment_suggestions(
    project_id: str,
    count: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get smart suggestions for best segments to export.

    Algorithm:
    1. Top score segments (highest viral potential)
    2. Monetizable segments (60s+ duration)
    3. Diverse tags (avoid repetitive content)
    """
    # Get all segments sorted by score
    result = await db.execute(
        select(Segment)
        .where(Segment.project_id == project_id)
        .order_by(Segment.score_total.desc())
    )
    all_segments = result.scalars().all()

    if not all_segments:
        return {"success": True, "data": {"suggestions": [], "reasons": {}}}

    suggestions = []
    reasons = {}
    used_tags = set()

    # Priority 1: Top score segments
    for seg in all_segments:
        if len(suggestions) >= count:
            break

        score = seg.score_total or 0
        duration = seg.duration or 0
        tags = seg.score_tags or []

        # Check for diversity - avoid segments with same primary tags
        primary_tag = tags[0].lower() if tags else None
        if primary_tag and primary_tag in used_tags:
            continue

        # Prefer monetizable (60s+) and high score (60+)
        if score >= 60 and duration >= 60:
            suggestions.append(seg.to_dict())
            reasons[seg.id] = "Haute viralité + Monétisable"
            if primary_tag:
                used_tags.add(primary_tag)

    # Priority 2: High score but short
    for seg in all_segments:
        if len(suggestions) >= count:
            break
        if seg.id in [s['id'] for s in suggestions]:
            continue

        score = seg.score_total or 0
        duration = seg.duration or 0

        if score >= 70:
            suggestions.append(seg.to_dict())
            reasons[seg.id] = f"Score exceptionnel ({int(score)})"

    # Priority 3: Monetizable with decent score
    for seg in all_segments:
        if len(suggestions) >= count:
            break
        if seg.id in [s['id'] for s in suggestions]:
            continue

        score = seg.score_total or 0
        duration = seg.duration or 0

        if duration >= 60 and score >= 50:
            suggestions.append(seg.to_dict())
            reasons[seg.id] = "Monétisable"

    # Fill remaining with top scores
    for seg in all_segments:
        if len(suggestions) >= count:
            break
        if seg.id in [s['id'] for s in suggestions]:
            continue

        suggestions.append(seg.to_dict())
        reasons[seg.id] = "Top score"

    return {
        "success": True,
        "data": {
            "suggestions": suggestions[:count],
            "reasons": reasons,
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


class UpdateTranscriptRequest(BaseModel):
    """Request to update segment transcript."""
    words: list[dict] | None = None  # [{word, start, end, confidence?}]
    text: str | None = None


@router.put("/{project_id}/segments/{segment_id}/transcript")
async def update_transcript(
    project_id: str,
    segment_id: str,
    request: UpdateTranscriptRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update segment transcript - for correcting transcription errors."""
    result = await db.execute(
        select(Segment)
        .where(Segment.id == segment_id)
        .where(Segment.project_id == project_id)
    )
    segment = result.scalar_one_or_none()

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Update transcript text
    if request.text is not None:
        segment.transcript = request.text

    # Update word timings if provided - store in transcript_segments
    if request.words is not None:
        # Build transcript_segments format expected by captions engine
        # Each segment contains: {text, start, end, words: [{word, start, end}]}
        segment.transcript_segments = [{
            "text": " ".join(w.get("word", "") for w in request.words),
            "start": request.words[0].get("start", 0) if request.words else 0,
            "end": request.words[-1].get("end", 0) if request.words else 0,
            "words": request.words,
        }]
        # Also update transcript text from words if not provided
        if request.text is None:
            segment.transcript = " ".join(w.get("word", "") for w in request.words)

    await db.commit()
    await db.refresh(segment)

    return {
        "success": True,
        "data": segment.to_dict(),
        "message": "Transcript updated successfully"
    }


class AnalyzeJumpCutsRequest(BaseModel):
    sensitivity: str = "normal"  # "light", "normal", "aggressive"
    min_silence_ms: int | None = None


@router.post("/{project_id}/segments/{segment_id}/analyze-jump-cuts")
async def analyze_jump_cuts(
    project_id: str,
    segment_id: str,
    request: AnalyzeJumpCutsRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Analyze a segment for potential jump cuts (preview before export)."""
    from forge_engine.services.jump_cuts import JumpCutConfig, JumpCutEngine

    # Get project
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get segment
    result = await db.execute(
        select(Segment)
        .where(Segment.id == segment_id)
        .where(Segment.project_id == project_id)
    )
    segment = result.scalar_one_or_none()

    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Build config
    config = JumpCutConfig.from_dict({
        "enabled": True,
        "sensitivity": request.sensitivity,
        "min_silence_ms": request.min_silence_ms,
    })

    # Run analysis
    jump_cut_engine = JumpCutEngine.get_instance()

    try:
        analysis = await jump_cut_engine.analyze_segment(
            audio_path=project.source_path,
            start_time=segment.start_time,
            duration=segment.duration,
            config=config,
        )

        return {
            "success": True,
            "data": {
                "original_duration": analysis.original_duration,
                "new_duration": analysis.new_duration,
                "cuts_count": analysis.cuts_count,
                "time_saved": analysis.time_saved,
                "time_saved_percent": analysis.time_saved_percent,
                "keep_ranges": [
                    {"start": r.start, "end": r.end, "duration": r.duration}
                    for r in analysis.keep_ranges
                ],
            }
        }
    except Exception as e:
        logger.error(f"Jump cut analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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

    # Debug log
    logger.info(f"[API] Export request - caption_style: {request.caption_style}")
    logger.info(f"[API] Export request - layout_config: {request.layout_config}")
    logger.info(f"[API] Export request - intro_config: {request.intro_config}")
    logger.info(f"[API] Export request - music_config: {request.music_config}")
    logger.info(f"[API] Export request - jump_cut_config: {request.jump_cut_config}")

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
        music_config=request.music_config.model_dump() if request.music_config else None,
        jump_cut_config=request.jump_cut_config.model_dump() if request.jump_cut_config else None,
    )

    return {"success": True, "data": {"jobId": job.id}}


class MultiExportRequest(BaseModel):
    """Request body for multi-variant export."""
    segment_id: str
    styles: list[str] | None = None  # Default: ["viral", "clean", "impact"]
    platform: str = "tiktok"
    include_captions: bool = True
    burn_subtitles: bool = True
    use_nvenc: bool = True
    layout_config: LayoutConfigRequest | None = None
    intro_config: IntroConfigRequest | None = None
    music_config: MusicConfigRequest | None = None


@router.post("/{project_id}/export-variants")
async def export_all_variants(
    project_id: str,
    request: MultiExportRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Export a segment with all 3 style variants (VIRAL, CLEAN, IMPACT)."""
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

    # Create multi-export job
    job_manager = JobManager.get_instance()
    export_service = ExportService()

    logger.info(f"[API] Multi-export request for segment {request.segment_id} with styles: {request.styles or ['viral', 'clean', 'impact']}")

    job = await job_manager.create_job(
        job_type=JobType.EXPORT,
        handler=export_service.generate_all_variants,
        project_id=project_id,
        segment_id=request.segment_id,
        styles=request.styles,
        platform=request.platform,
        include_captions=request.include_captions,
        burn_subtitles=request.burn_subtitles,
        use_nvenc=request.use_nvenc,
        layout_config=request.layout_config.model_dump() if request.layout_config else None,
        intro_config=request.intro_config.model_dump() if request.intro_config else None,
        music_config=request.music_config.model_dump() if request.music_config else None,
    )

    return {"success": True, "data": {"jobId": job.id, "variants": request.styles or ["viral", "clean", "impact"]}}


class BatchExportRequest(BaseModel):
    """Request body for batch export - WORLD CLASS one-click export."""
    min_score: float = 70.0  # Minimum score threshold
    max_clips: int = 500  # Maximum clips to export (no practical limit)
    style: str = "viral_pro"  # Caption style (default: world class)
    platform: str = "tiktok"
    include_captions: bool = True
    burn_subtitles: bool = True
    include_cover: bool = True
    include_metadata: bool = True
    use_nvenc: bool = True


@router.post("/{project_id}/export-all")
async def batch_export_all_clips(
    project_id: str,
    request: BatchExportRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    WORLD CLASS BATCH EXPORT - Export all high-scoring clips in one click.

    This is the simplified workflow for viral content creation:
    1. Analyzes all segments with score >= min_score
    2. Exports top max_clips with viral_pro style
    3. Generates covers and metadata automatically

    Returns job ID to track progress via WebSocket.
    """
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status not in ("analyzed", "ready"):
        raise HTTPException(status_code=400, detail="Project must be analyzed first")

    # Count available segments
    count_result = await db.execute(
        select(func.count())
        .select_from(Segment)
        .where(Segment.project_id == project_id)
        .where(Segment.score_total >= request.min_score)
    )
    available_count = count_result.scalar() or 0

    if available_count == 0:
        return {
            "success": True,
            "data": {
                "message": f"Aucun segment avec score >= {request.min_score}",
                "availableCount": 0
            }
        }

    # Create batch export job
    job_manager = JobManager.get_instance()
    export_service = ExportService()

    logger.info(f"[API] Batch export for project {project_id}: {available_count} segments available, exporting top {request.max_clips} with style '{request.style}'")

    job = await job_manager.create_job(
        job_type=JobType.EXPORT,
        handler=export_service.batch_export_all,
        project_id=project_id,
        min_score=request.min_score,
        max_clips=request.max_clips,
        style=request.style,
        platform=request.platform,
        include_captions=request.include_captions,
        burn_subtitles=request.burn_subtitles,
        include_cover=request.include_cover,
        include_metadata=request.include_metadata,
        use_nvenc=request.use_nvenc,
    )

    return {
        "success": True,
        "data": {
            "jobId": job.id,
            "availableCount": available_count,
            "willExport": min(available_count, request.max_clips),
            "style": request.style,
            "minScore": request.min_score
        }
    }


@router.get("/{project_id}/thumbnail")
async def get_project_thumbnail(
    project_id: str,
    time: float = Query(0, description="Time in seconds to extract thumbnail"),
    width: int = Query(320, ge=32, le=1920),
    height: int = Query(180, ge=32, le=1080),
    db: AsyncSession = Depends(get_db)
):
    """Generate a thumbnail from project video at specified time."""
    import hashlib
    import subprocess
    from pathlib import Path

    from fastapi.responses import FileResponse

    from forge_engine.core.config import settings

    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if project has a stored thumbnail
    if project.thumbnail_path and Path(project.thumbnail_path).exists():
        return FileResponse(
            project.thumbnail_path,
            media_type="image/jpeg"
        )

    # Try to find proxy or source video
    project_dir = settings.LIBRARY_PATH / "projects" / project_id
    proxy_path = project_dir / "proxy" / "proxy.mp4"
    source_path = Path(project.source_path) if project.source_path else None

    video_path = None
    if proxy_path.exists():
        video_path = proxy_path
    elif source_path and source_path.exists():
        video_path = source_path

    if not video_path:
        # Return placeholder
        raise HTTPException(status_code=404, detail="No video found for thumbnail")

    # Generate thumbnail using FFmpeg
    cache_dir = project_dir / "cache" / "thumbnails"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Cache key based on time and size
    cache_key = hashlib.md5(f"{time}_{width}_{height}".encode()).hexdigest()[:8]
    thumb_path = cache_dir / f"thumb_{cache_key}.jpg"

    if not thumb_path.exists():
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(max(0, time)),
                "-i", str(video_path),
                "-vframes", "1",
                "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                "-q:v", "3",
                str(thumb_path)
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate thumbnail")

    if thumb_path.exists():
        return FileResponse(thumb_path, media_type="image/jpeg")

    raise HTTPException(status_code=500, detail="Thumbnail generation failed")


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


@router.get("/{project_id}/artifacts/{artifact_id}/qc")
async def get_artifact_qc(
    project_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run QC check on a specific export artifact."""
    from forge_engine.core.config import settings
    from forge_engine.services.qc import QCService

    result = await db.execute(
        select(Artifact)
        .where(Artifact.id == artifact_id)
        .where(Artifact.project_id == project_id)
    )
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = Path(artifact.path)
    qc = QCService()
    report = await qc.run(
        file_path=file_path,
        ffprobe_path=settings.FFPROBE_PATH,
    )
    return report.to_dict()


@router.get("/{project_id}/artifacts/{artifact_id}/file")
async def serve_artifact_file(
    project_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Serve an artifact file (video, cover, etc.)."""
    from pathlib import Path

    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    result = await db.execute(
        select(Artifact)
        .where(Artifact.id == artifact_id)
        .where(Artifact.project_id == project_id)
    )
    artifact = result.scalar_one_or_none()

    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path = Path(artifact.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Determine media type based on artifact type
    media_types = {
        "video": "video/mp4",
        "cover": "image/jpeg",
        "thumbnail": "image/jpeg",
        "audio": "audio/wav",
    }
    media_type = media_types.get(artifact.type, "application/octet-stream")

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=artifact.filename
    )






