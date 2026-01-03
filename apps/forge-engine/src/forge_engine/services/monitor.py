"""System monitoring service - L'ŒIL.

Monitors all system components, jobs, and provides auto-recovery.
"""

import asyncio
import logging
import os
import platform
import psutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """A log entry."""
    timestamp: datetime
    level: str
    source: str
    message: str
    extra: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "extra": self.extra,
        }


@dataclass
class SystemStats:
    """System statistics."""
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    gpu_memory_used_gb: float = 0
    gpu_memory_total_gb: float = 0
    gpu_utilization: float = 0
    
    def to_dict(self) -> dict:
        return {
            "cpu": {
                "percent": self.cpu_percent,
            },
            "memory": {
                "percent": self.memory_percent,
                "usedGb": round(self.memory_used_gb, 2),
                "totalGb": round(self.memory_total_gb, 2),
            },
            "disk": {
                "percent": self.disk_percent,
                "usedGb": round(self.disk_used_gb, 2),
                "totalGb": round(self.disk_total_gb, 2),
            },
            "gpu": {
                "available": self.gpu_available,
                "name": self.gpu_name,
                "memoryUsedGb": round(self.gpu_memory_used_gb, 2),
                "memoryTotalGb": round(self.gpu_memory_total_gb, 2),
                "utilization": self.gpu_utilization,
            },
        }


@dataclass
class ServiceHealth:
    """Health status of a service."""
    name: str
    status: str  # healthy, degraded, unhealthy, unknown
    last_check: datetime
    message: Optional[str] = None
    latency_ms: float = 0
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "lastCheck": self.last_check.isoformat(),
            "message": self.message,
            "latencyMs": round(self.latency_ms, 2),
        }


@dataclass
class JobHealth:
    """Health info for a job."""
    job_id: str
    job_type: str
    status: str
    progress: float
    started_at: Optional[datetime]
    last_update: Optional[datetime]
    is_stuck: bool = False
    stuck_duration_seconds: float = 0
    
    def to_dict(self) -> dict:
        return {
            "jobId": self.job_id,
            "jobType": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "lastUpdate": self.last_update.isoformat() if self.last_update else None,
            "isStuck": self.is_stuck,
            "stuckDurationSeconds": self.stuck_duration_seconds,
        }


class MonitorService:
    """L'ŒIL - System monitoring and auto-recovery service."""
    
    _instance: Optional["MonitorService"] = None
    
    # Configuration
    JOB_STUCK_THRESHOLD_SECONDS = 180  # 3 minutes without progress = stuck
    PROJECT_STUCK_THRESHOLD_SECONDS = 600  # 10 minutes in transient state = stuck
    LOG_BUFFER_SIZE = 1000  # Keep last 1000 log entries
    HEALTH_CHECK_INTERVAL = 15  # seconds - check more frequently
    AUTO_RECOVERY_ENABLED = True  # Enable automatic recovery
    AUTO_RETRY_MAX = 3  # Maximum auto-retry attempts
    
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._logs: deque[LogEntry] = deque(maxlen=self.LOG_BUFFER_SIZE)
        self._services_health: Dict[str, ServiceHealth] = {}
        self._jobs_health: Dict[str, JobHealth] = {}
        self._last_job_progress: Dict[str, tuple[float, datetime]] = {}
        self._event_handlers: List[Callable] = []
        self._start_time = datetime.now()
        
        # Setup log capture
        self._setup_log_capture()
    
    @classmethod
    def get_instance(cls) -> "MonitorService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _setup_log_capture(self):
        """Setup logging handler to capture all logs."""
        class MonitorHandler(logging.Handler):
            def __init__(self, monitor: "MonitorService"):
                super().__init__()
                self.monitor = monitor
            
            def emit(self, record: logging.LogRecord):
                try:
                    entry = LogEntry(
                        timestamp=datetime.fromtimestamp(record.created),
                        level=record.levelname,
                        source=record.name,
                        message=record.getMessage(),
                        extra={
                            "filename": record.filename,
                            "lineno": record.lineno,
                            "funcName": record.funcName,
                        } if record.levelno >= logging.WARNING else None
                    )
                    self.monitor._logs.append(entry)
                    
                    # Broadcast to WebSocket if error/warning
                    if record.levelno >= logging.WARNING:
                        self.monitor._broadcast_log(entry)
                except Exception:
                    pass
        
        # Add handler to root logger
        handler = MonitorHandler(self)
        handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)
    
    def _broadcast_log(self, entry: LogEntry):
        """Broadcast log entry to WebSocket clients."""
        try:
            from forge_engine.api.v1.endpoints.websockets import manager
            import asyncio
            
            message = {
                "type": "MONITOR_LOG",
                "payload": entry.to_dict()
            }
            
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(manager.broadcast(message))
            except RuntimeError:
                pass
        except Exception:
            pass
    
    def log(self, level: str, source: str, message: str, extra: Optional[dict] = None):
        """Add a log entry manually."""
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level.upper(),
            source=source,
            message=message,
            extra=extra
        )
        self._logs.append(entry)
        
        if level.upper() in ("WARNING", "ERROR", "CRITICAL"):
            self._broadcast_log(entry)
    
    def get_logs(self, limit: int = 100, level: Optional[str] = None, source: Optional[str] = None) -> List[dict]:
        """Get recent logs with optional filtering."""
        logs = list(self._logs)
        
        if level:
            logs = [l for l in logs if l.level == level.upper()]
        if source:
            logs = [l for l in logs if source.lower() in l.source.lower()]
        
        # Return most recent first
        return [l.to_dict() for l in reversed(logs[-limit:])]
    
    def get_system_stats(self) -> SystemStats:
        """Get current system statistics."""
        # CPU and Memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Disk (main drive)
        disk = psutil.disk_usage(str(Path.home()))
        
        stats = SystemStats(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            disk_percent=disk.percent,
            disk_used_gb=disk.used / (1024**3),
            disk_total_gb=disk.total / (1024**3),
        )
        
        # GPU stats (if available)
        try:
            import torch
            if torch.cuda.is_available():
                stats.gpu_available = True
                stats.gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                stats.gpu_memory_total_gb = props.total_memory / (1024**3)
                
                # Get current memory usage
                stats.gpu_memory_used_gb = torch.cuda.memory_allocated(0) / (1024**3)
                
                # Try to get utilization via nvidia-smi
                try:
                    import subprocess
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=2
                    )
                    if result.returncode == 0:
                        stats.gpu_utilization = float(result.stdout.strip())
                except Exception:
                    pass
        except ImportError:
            pass
        
        return stats
    
    async def check_service_health(self, name: str, check_func: Callable) -> ServiceHealth:
        """Check health of a service."""
        start = time.time()
        try:
            result = await check_func() if asyncio.iscoroutinefunction(check_func) else check_func()
            latency = (time.time() - start) * 1000
            
            if result:
                health = ServiceHealth(
                    name=name,
                    status="healthy",
                    last_check=datetime.now(),
                    latency_ms=latency
                )
            else:
                health = ServiceHealth(
                    name=name,
                    status="unhealthy",
                    last_check=datetime.now(),
                    message="Check returned False",
                    latency_ms=latency
                )
        except Exception as e:
            health = ServiceHealth(
                name=name,
                status="unhealthy",
                last_check=datetime.now(),
                message=str(e)[:200],
                latency_ms=(time.time() - start) * 1000
            )
        
        self._services_health[name] = health
        return health
    
    async def check_all_services(self) -> Dict[str, ServiceHealth]:
        """Check health of all registered services."""
        from forge_engine.services.ffmpeg import FFmpegService
        from forge_engine.services.transcription import TranscriptionService
        from forge_engine.core.database import engine
        
        # FFmpeg
        ffmpeg = FFmpegService()
        await self.check_service_health("ffmpeg", ffmpeg.check_availability)
        
        # Whisper
        transcription = TranscriptionService()
        await self.check_service_health("whisper", lambda: transcription.is_available())
        
        # Database
        async def check_db():
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")
            return True
        await self.check_service_health("database", check_db)
        
        return self._services_health
    
    def update_job_health(self, job_id: str, job_type: str, status: str, progress: float, started_at: Optional[datetime] = None):
        """Update job health info."""
        now = datetime.now()
        
        # Check if stuck
        is_stuck = False
        stuck_duration = 0
        
        if job_id in self._last_job_progress:
            last_progress, last_time = self._last_job_progress[job_id]
            if progress == last_progress and status == "running":
                stuck_duration = (now - last_time).total_seconds()
                if stuck_duration > self.JOB_STUCK_THRESHOLD_SECONDS:
                    is_stuck = True
                    self.log("WARNING", "monitor", f"Job {job_id[:8]} appears stuck for {stuck_duration:.0f}s")
            else:
                self._last_job_progress[job_id] = (progress, now)
        else:
            self._last_job_progress[job_id] = (progress, now)
        
        self._jobs_health[job_id] = JobHealth(
            job_id=job_id,
            job_type=job_type,
            status=status,
            progress=progress,
            started_at=started_at,
            last_update=now,
            is_stuck=is_stuck,
            stuck_duration_seconds=stuck_duration
        )
    
    def get_jobs_health(self) -> List[dict]:
        """Get health info for all tracked jobs."""
        return [j.to_dict() for j in self._jobs_health.values()]
    
    def get_stuck_jobs(self) -> List[JobHealth]:
        """Get list of stuck jobs."""
        return [j for j in self._jobs_health.values() if j.is_stuck]
    
    async def recover_stuck_jobs(self) -> int:
        """Attempt to recover stuck jobs and restart them."""
        from forge_engine.core.database import async_session_maker
        from forge_engine.models import Project
        from forge_engine.models.job import JobRecord
        from sqlalchemy import select, update
        
        stuck_jobs = self.get_stuck_jobs()
        recovered = 0
        
        async with async_session_maker() as db:
            for job in stuck_jobs:
                try:
                    # Get the job record
                    result = await db.execute(
                        select(JobRecord).where(JobRecord.id == job.job_id)
                    )
                    job_record = result.scalar_one_or_none()
                    
                    if not job_record:
                        continue
                    
                    # Mark job as failed
                    await db.execute(
                        update(JobRecord)
                        .where(JobRecord.id == job.job_id)
                        .values(
                            status="failed", 
                            error=f"Auto-recovered: stuck for {job.stuck_duration_seconds:.0f}s"
                        )
                    )
                    
                    # Get associated project
                    project_result = await db.execute(
                        select(Project).where(Project.id == job_record.project_id)
                    )
                    project = project_result.scalar_one_or_none()
                    
                    if project:
                        # Reset project to appropriate state based on job type
                        if job.job_type == "ingest":
                            project.status = "created"
                        elif job.job_type == "analyze":
                            project.status = "ingested"
                        elif job.job_type == "export":
                            project.status = "analyzed"
                        
                        self.log("INFO", "monitor", f"Reset project {project.id[:8]} to '{project.status}'")
                    
                    # Clean up tracking
                    if job.job_id in self._jobs_health:
                        del self._jobs_health[job.job_id]
                    if job.job_id in self._last_job_progress:
                        del self._last_job_progress[job.job_id]
                    
                    recovered += 1
                    self.log("INFO", "monitor", f"Recovered stuck job: {job.job_id[:8]} ({job.job_type})")
                    
                except Exception as e:
                    self.log("ERROR", "monitor", f"Failed to recover job {job.job_id[:8]}: {e}")
            
            await db.commit()
        
        return recovered
    
    async def recover_stuck_projects(self) -> int:
        """Recover projects stuck in transient states."""
        from forge_engine.core.database import async_session_maker
        from forge_engine.models import Project
        from forge_engine.models.job import JobRecord
        from sqlalchemy import select, and_
        
        recovered = 0
        transient_states = ["ingesting", "analyzing", "downloading", "exporting"]
        
        async with async_session_maker() as db:
            # Find projects in transient states
            result = await db.execute(
                select(Project).where(Project.status.in_(transient_states))
            )
            projects = result.scalars().all()
            
            for project in projects:
                try:
                    # Check if there's an active job for this project
                    job_result = await db.execute(
                        select(JobRecord).where(
                            and_(
                                JobRecord.project_id == project.id,
                                JobRecord.status.in_(["pending", "running"])
                            )
                        )
                    )
                    active_job = job_result.scalar_one_or_none()
                    
                    if not active_job:
                        # No active job - project is orphaned, reset it
                        old_status = project.status
                        
                        if old_status in ["ingesting", "downloading"]:
                            project.status = "created"
                        elif old_status == "analyzing":
                            project.status = "ingested"
                        elif old_status == "exporting":
                            project.status = "analyzed"
                        
                        self.log("WARNING", "monitor", 
                            f"Recovered orphaned project {project.id[:8]}: '{old_status}' -> '{project.status}'")
                        recovered += 1
                    
                except Exception as e:
                    self.log("ERROR", "monitor", f"Failed to check project {project.id[:8]}: {e}")
            
            await db.commit()
        
        return recovered
    
    async def auto_restart_failed_jobs(self) -> int:
        """Auto-restart recently failed jobs that haven't exceeded retry limit."""
        from forge_engine.core.database import async_session_maker
        from forge_engine.models import Project
        from forge_engine.models.job import JobRecord
        from forge_engine.core.jobs import JobManager, JobType
        from sqlalchemy import select, and_
        
        restarted = 0
        
        # Only restart jobs that failed in the last 10 minutes
        cutoff = datetime.now() - timedelta(minutes=10)
        
        async with async_session_maker() as db:
            result = await db.execute(
                select(JobRecord).where(
                    and_(
                        JobRecord.status == "failed",
                        JobRecord.completed_at > cutoff
                    )
                ).order_by(JobRecord.completed_at.desc()).limit(10)
            )
            failed_jobs = result.scalars().all()
            
            for job_record in failed_jobs:
                try:
                    # Check retry count in metadata
                    retry_count = 0
                    if job_record.result and isinstance(job_record.result, dict):
                        retry_count = job_record.result.get("_retry_count", 0)
                    
                    if retry_count >= self.AUTO_RETRY_MAX:
                        continue
                    
                    # Get project
                    project_result = await db.execute(
                        select(Project).where(Project.id == job_record.project_id)
                    )
                    project = project_result.scalar_one_or_none()
                    
                    if not project:
                        continue
                    
                    # Check if there's already a new job for this project
                    existing_result = await db.execute(
                        select(JobRecord).where(
                            and_(
                                JobRecord.project_id == project.id,
                                JobRecord.type == job_record.type,
                                JobRecord.status.in_(["pending", "running"]),
                                JobRecord.created_at > job_record.completed_at
                            )
                        )
                    )
                    if existing_result.scalar_one_or_none():
                        continue  # Already has a replacement job
                    
                    # Restart the job
                    job_manager = JobManager.get_instance()
                    
                    if job_record.type == "ingest":
                        from forge_engine.services.ingest import IngestService
                        service = IngestService()
                        await job_manager.create_job(
                            job_type=JobType.INGEST,
                            handler=service.run_ingest,
                            project_id=project.id,
                            auto_analyze=True,
                            _retry_count=retry_count + 1
                        )
                        project.status = "ingesting"
                        
                    elif job_record.type == "analyze":
                        from forge_engine.services.analysis import AnalysisService
                        service = AnalysisService()
                        await job_manager.create_job(
                            job_type=JobType.ANALYZE,
                            handler=service.run_analysis,
                            project_id=project.id,
                            _retry_count=retry_count + 1
                        )
                        project.status = "analyzing"
                    
                    await db.commit()
                    restarted += 1
                    self.log("INFO", "monitor", 
                        f"Auto-restarted {job_record.type} job for project {project.id[:8]} (retry #{retry_count + 1})")
                    
                except Exception as e:
                    self.log("ERROR", "monitor", f"Failed to restart job: {e}")
        
        return restarted
    
    async def ensure_workflow_continuity(self) -> dict:
        """Ensure all projects are progressing through their workflow."""
        from forge_engine.core.database import async_session_maker
        from forge_engine.models import Project
        from forge_engine.models.job import JobRecord
        from forge_engine.core.jobs import JobManager, JobType
        from sqlalchemy import select, and_, not_
        
        stats = {"ingested_without_analysis": 0, "actions_taken": 0}
        
        async with async_session_maker() as db:
            # Find projects that are "ingested" but have no pending/running analysis job
            result = await db.execute(
                select(Project).where(Project.status == "ingested")
            )
            ingested_projects = result.scalars().all()
            
            for project in ingested_projects:
                # Check if there's a pending/running analysis job
                job_result = await db.execute(
                    select(JobRecord).where(
                        and_(
                            JobRecord.project_id == project.id,
                            JobRecord.type == "analyze",
                            JobRecord.status.in_(["pending", "running"])
                        )
                    )
                )
                
                if not job_result.scalar_one_or_none():
                    stats["ingested_without_analysis"] += 1
                    
                    # Check project metadata for auto_analyze flag
                    auto_analyze = True
                    if project.project_meta and isinstance(project.project_meta, dict):
                        auto_analyze = project.project_meta.get("auto_analyze", True)
                    
                    if auto_analyze and self.AUTO_RECOVERY_ENABLED:
                        # Auto-start analysis
                        try:
                            from forge_engine.services.analysis import AnalysisService
                            job_manager = JobManager.get_instance()
                            service = AnalysisService()
                            
                            await job_manager.create_job(
                                job_type=JobType.ANALYZE,
                                handler=service.run_analysis,
                                project_id=project.id,
                            )
                            
                            project.status = "analyzing"
                            await db.commit()
                            
                            stats["actions_taken"] += 1
                            self.log("INFO", "monitor", 
                                f"Auto-started analysis for project {project.id[:8]}")
                            
                        except Exception as e:
                            self.log("ERROR", "monitor", f"Failed to auto-start analysis: {e}")
        
        return stats
    
    def get_uptime(self) -> float:
        """Get service uptime in seconds."""
        return (datetime.now() - self._start_time).total_seconds()
    
    def get_full_status(self) -> dict:
        """Get full system status."""
        return {
            "uptime": self.get_uptime(),
            "uptimeFormatted": self._format_uptime(self.get_uptime()),
            "system": self.get_system_stats().to_dict(),
            "services": {name: h.to_dict() for name, h in self._services_health.items()},
            "jobs": {
                "total": len(self._jobs_health),
                "stuck": len(self.get_stuck_jobs()),
                "items": self.get_jobs_health()
            },
            "logs": {
                "total": len(self._logs),
                "errors": sum(1 for l in self._logs if l.level in ("ERROR", "CRITICAL")),
                "warnings": sum(1 for l in self._logs if l.level == "WARNING"),
            }
        }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human readable string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    async def start(self):
        """Start the monitoring background task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        self.log("INFO", "monitor", "L'ŒIL monitoring service started")
    
    async def stop(self):
        """Stop the monitoring background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.log("INFO", "monitor", "L'ŒIL monitoring service stopped")
    
    async def _monitor_loop(self):
        """Background monitoring loop with comprehensive auto-recovery."""
        cycle_count = 0
        
        while self._running:
            try:
                cycle_count += 1
                
                # Check services health
                await self.check_all_services()
                
                # === AUTO-RECOVERY PIPELINE ===
                if self.AUTO_RECOVERY_ENABLED:
                    
                    # 1. Recover stuck jobs (every cycle)
                    stuck = self.get_stuck_jobs()
                    if stuck:
                        self.log("WARNING", "recovery", f"Found {len(stuck)} stuck job(s), attempting recovery...")
                        recovered = await self.recover_stuck_jobs()
                        if recovered > 0:
                            self.log("INFO", "recovery", f"Recovered {recovered} stuck job(s)")
                    
                    # 2. Recover orphaned projects (every cycle)
                    orphaned = await self.recover_stuck_projects()
                    if orphaned > 0:
                        self.log("INFO", "recovery", f"Recovered {orphaned} orphaned project(s)")
                    
                    # 3. Auto-restart failed jobs (every 2 cycles = 30s)
                    if cycle_count % 2 == 0:
                        restarted = await self.auto_restart_failed_jobs()
                        if restarted > 0:
                            self.log("INFO", "recovery", f"Auto-restarted {restarted} failed job(s)")
                    
                    # 4. Ensure workflow continuity (every 4 cycles = 60s)
                    if cycle_count % 4 == 0:
                        workflow_stats = await self.ensure_workflow_continuity()
                        if workflow_stats["actions_taken"] > 0:
                            self.log("INFO", "recovery", 
                                f"Workflow continuity: {workflow_stats['actions_taken']} action(s) taken")
                
                # Broadcast status update to WebSocket clients
                try:
                    from forge_engine.api.v1.endpoints.websockets import manager
                    status = self.get_full_status()
                    status["autoRecovery"] = {
                        "enabled": self.AUTO_RECOVERY_ENABLED,
                        "cycleCount": cycle_count,
                    }
                    message = {
                        "type": "MONITOR_STATUS",
                        "payload": status
                    }
                    await manager.broadcast(message)
                except Exception:
                    pass
                
            except Exception as e:
                self.log("ERROR", "monitor", f"Monitor loop error: {e}")
            
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)

