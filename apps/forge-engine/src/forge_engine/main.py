"""FORGE Engine - Main FastAPI Application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from forge_engine.api.v1.router import api_router
from forge_engine.core.config import settings
from forge_engine.core.database import init_db, close_db
from forge_engine.core.jobs import JobManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def cleanup_orphan_ffmpeg():
    """Kill orphan FFmpeg processes from previous runs."""
    import platform
    if platform.system() == "Windows":
        try:
            proc = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/IM", "ffmpeg.exe",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
            if proc.returncode == 0:
                logger.info("Cleaned up orphan FFmpeg processes")
        except Exception as e:
            logger.debug("No orphan FFmpeg to clean: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting FORGE Engine v%s", settings.VERSION)
    
    # Clean up any orphan FFmpeg processes from crashed runs
    await cleanup_orphan_ffmpeg()
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start job manager
    job_manager = JobManager.get_instance()
    
    # Register WebSocket listener and set main loop for thread-safe callbacks
    from forge_engine.api.v1.endpoints.websockets import job_update_listener, set_main_loop
    main_loop = asyncio.get_running_loop()
    set_main_loop(main_loop)
    job_manager.set_main_loop(main_loop)  # Also store in JobManager for DB updates
    job_manager.register_global_listener(job_update_listener)
    
    # Register job handlers
    from forge_engine.services.ingest import IngestService
    from forge_engine.services.analysis import AnalysisService
    from forge_engine.services.export import ExportService
    from forge_engine.core.jobs import JobType
    
    ingest_service = IngestService()
    analysis_service = AnalysisService()
    export_service = ExportService()
    
    job_manager.register_handler(JobType.INGEST, ingest_service.run_ingest)
    job_manager.register_handler(JobType.ANALYZE, analysis_service.run_analysis)
    job_manager.register_handler(JobType.EXPORT, export_service.run_export)
    
    asyncio.create_task(job_manager.start())
    logger.info("Job manager started")
    
    # Check FFmpeg
    from forge_engine.services.ffmpeg import FFmpegService
    ffmpeg = FFmpegService()
    if await ffmpeg.check_availability():
        logger.info("FFmpeg available - NVENC: %s", ffmpeg.has_nvenc)
    else:
        logger.warning("FFmpeg not found! Video processing will fail.")
    
    # Start L'ŒIL monitoring service
    from forge_engine.services.monitor import MonitorService
    monitor = MonitorService.get_instance()
    await monitor.start()
    logger.info("L'ŒIL monitoring service started")
    
    yield
    
    # Cleanup
    logger.info("Shutting down FORGE Engine...")
    await monitor.stop()
    await job_manager.stop()
    await close_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="FORGE Engine",
        description="Viral clip processing backend for FORGE/LAB",
        version=settings.VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        from forge_engine.services.ffmpeg import FFmpegService
        from forge_engine.services.transcription import TranscriptionService
        
        ffmpeg = FFmpegService()
        transcription = TranscriptionService()
        
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "services": {
                "ffmpeg": await ffmpeg.check_availability(),
                "whisper": transcription.is_available(),
                "nvenc": ffmpeg.has_nvenc,
                "database": True,
            },
        }
    
    # Include API router
    app.include_router(api_router, prefix="/v1")
    
    # Mount static files for library (video serving)
    library_path = settings.LIBRARY_PATH
    if library_path.exists():
        app.mount("/library", StaticFiles(directory=str(library_path)), name="library")
        logger.info("Library mounted at /library: %s", library_path)
    
    # Serve project files
    @app.get("/media/{project_id}/{file_type}")
    async def serve_media(project_id: str, file_type: str):
        """Serve project media files (proxy, audio, source)."""
        from fastapi import HTTPException
        
        project_dir = library_path / "projects" / project_id
        
        # Try multiple possible locations
        possible_paths = {
            "proxy": [
                project_dir / "proxy" / "proxy.mp4",
                project_dir / "proxy.mp4",
            ],
            "audio": [
                project_dir / "audio" / "audio.wav",
                project_dir / "audio.wav",
            ],
        }
        
        paths_to_try = possible_paths.get(file_type, [])
        
        for file_path in paths_to_try:
            if file_path.exists():
                media_type = "video/mp4" if file_type == "proxy" else "audio/wav"
                return FileResponse(file_path, media_type=media_type)
        
        # Log what we tried
        logger.warning("Media not found for %s/%s. Tried: %s", project_id, file_type, paths_to_try)
        raise HTTPException(status_code=404, detail=f"File not found: {file_type}")
    
    return app


# Create app instance
app = create_app()


def main():
    """Run the application."""
    import uvicorn
    
    uvicorn.run(
        "forge_engine.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )


if __name__ == "__main__":
    main()





