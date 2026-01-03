"""Monitor/Admin endpoints - L'ŒIL."""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from forge_engine.services.monitor import MonitorService

router = APIRouter()


class RecoverRequest(BaseModel):
    job_ids: Optional[list[str]] = None  # If None, recover all stuck jobs


@router.get("/status")
async def get_status() -> dict:
    """Get full system status."""
    monitor = MonitorService.get_instance()
    return {
        "success": True,
        "data": monitor.get_full_status()
    }


@router.get("/stats")
async def get_stats() -> dict:
    """Get system statistics."""
    monitor = MonitorService.get_instance()
    return {
        "success": True,
        "data": monitor.get_system_stats().to_dict()
    }


@router.get("/logs")
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    level: Optional[str] = None,
    source: Optional[str] = None
) -> dict:
    """Get recent logs."""
    monitor = MonitorService.get_instance()
    return {
        "success": True,
        "data": monitor.get_logs(limit=limit, level=level, source=source)
    }


@router.get("/services")
async def get_services_health() -> dict:
    """Get health status of all services."""
    monitor = MonitorService.get_instance()
    await monitor.check_all_services()
    return {
        "success": True,
        "data": {name: h.to_dict() for name, h in monitor._services_health.items()}
    }


@router.get("/jobs")
async def get_jobs_health() -> dict:
    """Get health info for all tracked jobs."""
    monitor = MonitorService.get_instance()
    return {
        "success": True,
        "data": {
            "items": monitor.get_jobs_health(),
            "stuck": [j.to_dict() for j in monitor.get_stuck_jobs()]
        }
    }


@router.post("/recover")
async def recover_stuck_jobs(request: Optional[RecoverRequest] = None) -> dict:
    """Recover stuck jobs."""
    monitor = MonitorService.get_instance()
    recovered = await monitor.recover_stuck_jobs()
    return {
        "success": True,
        "data": {
            "recovered": recovered
        }
    }


@router.post("/reset-project/{project_id}")
async def reset_project_status(project_id: str, status: str = "ingested") -> dict:
    """Reset a project's status."""
    from forge_engine.core.database import async_session_maker
    from forge_engine.models import Project
    from sqlalchemy import select
    
    valid_statuses = ["created", "ingested", "analyzed", "ready"]
    if status not in valid_statuses:
        return {"success": False, "error": f"Invalid status. Must be one of: {valid_statuses}"}
    
    async with async_session_maker() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        
        if not project:
            return {"success": False, "error": "Project not found"}
        
        old_status = project.status
        project.status = status
        await db.commit()
        
        monitor = MonitorService.get_instance()
        monitor.log("INFO", "admin", f"Reset project {project_id[:8]} from '{old_status}' to '{status}'")
        
        return {
            "success": True,
            "data": {
                "projectId": project_id,
                "oldStatus": old_status,
                "newStatus": status
            }
        }


@router.post("/cleanup-jobs")
async def cleanup_old_jobs(days: int = 7) -> dict:
    """Clean up old completed/failed jobs."""
    from datetime import datetime, timedelta
    from forge_engine.core.database import async_session_maker
    from forge_engine.models.job import JobRecord
    from sqlalchemy import delete
    
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    async with async_session_maker() as db:
        result = await db.execute(
            delete(JobRecord)
            .where(JobRecord.status.in_(["completed", "failed", "cancelled"]))
            .where(JobRecord.created_at < cutoff)
        )
        deleted = result.rowcount
        await db.commit()
        
        monitor = MonitorService.get_instance()
        monitor.log("INFO", "admin", f"Cleaned up {deleted} old jobs (older than {days} days)")
        
        return {
            "success": True,
            "data": {
                "deleted": deleted,
                "cutoffDays": days
            }
        }


@router.post("/log")
async def add_log(level: str, source: str, message: str) -> dict:
    """Add a manual log entry."""
    monitor = MonitorService.get_instance()
    monitor.log(level, source, message)
    return {"success": True}


@router.get("/auto-recovery")
async def get_auto_recovery_status() -> dict:
    """Get auto-recovery configuration and status."""
    monitor = MonitorService.get_instance()
    return {
        "success": True,
        "data": {
            "enabled": monitor.AUTO_RECOVERY_ENABLED,
            "jobStuckThresholdSeconds": monitor.JOB_STUCK_THRESHOLD_SECONDS,
            "projectStuckThresholdSeconds": monitor.PROJECT_STUCK_THRESHOLD_SECONDS,
            "autoRetryMax": monitor.AUTO_RETRY_MAX,
            "healthCheckIntervalSeconds": monitor.HEALTH_CHECK_INTERVAL,
        }
    }


@router.post("/auto-recovery/toggle")
async def toggle_auto_recovery(enabled: bool = True) -> dict:
    """Enable or disable auto-recovery."""
    monitor = MonitorService.get_instance()
    monitor.AUTO_RECOVERY_ENABLED = enabled
    monitor.log("INFO", "admin", f"Auto-recovery {'enabled' if enabled else 'disabled'}")
    return {
        "success": True,
        "data": {"enabled": monitor.AUTO_RECOVERY_ENABLED}
    }


@router.post("/force-workflow-check")
async def force_workflow_check() -> dict:
    """Force an immediate workflow continuity check."""
    monitor = MonitorService.get_instance()
    
    results = {
        "stuckJobs": await monitor.recover_stuck_jobs(),
        "stuckProjects": await monitor.recover_stuck_projects(),
        "restartedJobs": await monitor.auto_restart_failed_jobs(),
        "workflowActions": (await monitor.ensure_workflow_continuity())["actions_taken"],
    }
    
    monitor.log("INFO", "admin", f"Force workflow check: {results}")
    
    return {
        "success": True,
        "data": results
    }


@router.post("/restart-project/{project_id}")
async def restart_project_workflow(project_id: str, from_step: str = "ingest") -> dict:
    """Restart a project's workflow from a specific step."""
    from forge_engine.core.database import async_session_maker
    from forge_engine.models import Project
    from forge_engine.core.jobs import JobManager, JobType
    from sqlalchemy import select
    
    monitor = MonitorService.get_instance()
    
    valid_steps = ["ingest", "analyze"]
    if from_step not in valid_steps:
        return {"success": False, "error": f"Invalid step. Must be one of: {valid_steps}"}
    
    async with async_session_maker() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        
        if not project:
            return {"success": False, "error": "Project not found"}
        
        job_manager = JobManager.get_instance()
        
        if from_step == "ingest":
            from forge_engine.services.ingest import IngestService
            service = IngestService()
            job = await job_manager.create_job(
                job_type=JobType.INGEST,
                handler=service.run_ingest,
                project_id=project.id,
                auto_analyze=True,
            )
            project.status = "ingesting"
            
        elif from_step == "analyze":
            from forge_engine.services.analysis import AnalysisService
            service = AnalysisService()
            job = await job_manager.create_job(
                job_type=JobType.ANALYZE,
                handler=service.run_analysis,
                project_id=project.id,
            )
            project.status = "analyzing"
        
        await db.commit()
        
        monitor.log("INFO", "admin", f"Restarted project {project_id[:8]} from '{from_step}'")
        
        return {
            "success": True,
            "data": {
                "projectId": project_id,
                "fromStep": from_step,
                "jobId": job.id,
                "newStatus": project.status
            }
        }

