"""Job endpoints."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from forge_engine.core.jobs import JobManager

router = APIRouter()


@router.get("")
async def list_jobs(project_id: Optional[str] = Query(None)) -> dict:
    """List jobs, optionally filtered by project."""
    job_manager = JobManager.get_instance()
    
    if project_id:
        jobs = await job_manager.get_jobs_for_project(project_id)
    else:
        # Get all jobs from DB (last 100)
        jobs = await job_manager.get_all_jobs()
    
    return {"success": True, "data": [j.to_dict() for j in jobs]}


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    """Get job status and progress."""
    job_manager = JobManager.get_instance()
    job = await job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {"success": True, "data": job.to_dict()}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    """Cancel a job."""
    job_manager = JobManager.get_instance()
    cancelled = await job_manager.cancel_job(job_id)
    
    if not cancelled:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    
    return {"success": True, "data": {"cancelled": True}}






