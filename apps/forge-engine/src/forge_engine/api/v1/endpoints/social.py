"""Social Publishing API endpoints."""


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forge_engine.services.social_publish import SocialPublishService

router = APIRouter()


class ConnectAccountRequest(BaseModel):
    """Request to connect a social account."""
    platform: str  # "tiktok", "youtube", "instagram"
    credentials: dict[str, str]


class PublishRequest(BaseModel):
    """Request to publish content."""
    platform: str
    video_path: str
    title: str
    description: str | None = None
    hashtags: list[str] | None = None
    schedule_time: str | None = None  # ISO format datetime
    visibility: str = "public"  # "public", "private", "unlisted"


class PublishStatusResponse(BaseModel):
    """Publish job status."""
    job_id: str
    platform: str
    status: str
    url: str | None = None
    error: str | None = None


@router.get("/status")
async def get_social_status():
    """Get social publishing status and connected accounts."""
    service = SocialPublishService.get_instance()

    return {
        "available": True,
        "connected_accounts": service.get_connected_platforms(),
        "supported_platforms": ["tiktok", "youtube", "instagram"]
    }


@router.get("/accounts")
async def list_accounts():
    """List connected social accounts."""
    service = SocialPublishService.get_instance()

    accounts = service.get_connected_platforms()

    return {
        "accounts": accounts,
        "count": len(accounts)
    }


@router.post("/accounts/connect")
async def connect_account(request: ConnectAccountRequest):
    """Connect a new social account."""
    service = SocialPublishService.get_instance()

    if request.platform not in ["tiktok", "youtube", "instagram"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform: {request.platform}"
        )

    success = await service.connect_account(
        platform=request.platform,
        credentials=request.credentials
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to connect account"
        )

    return {
        "success": True,
        "platform": request.platform,
        "message": "Account connected successfully"
    }


@router.delete("/accounts/{platform}")
async def disconnect_account(platform: str):
    """Disconnect a social account."""
    service = SocialPublishService.get_instance()

    success = await service.disconnect_account(platform)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"No account connected for platform: {platform}"
        )

    return {
        "success": True,
        "message": f"Disconnected from {platform}"
    }


@router.post("/publish")
async def publish_content(request: PublishRequest):
    """Publish content to a social platform."""
    from datetime import datetime as _dt

    from forge_engine.services.social_publish import Platform
    from forge_engine.services.social_publish import PublishRequest as PublishJob

    service = SocialPublishService.get_instance()

    if request.platform not in service.get_connected_platforms():
        raise HTTPException(
            status_code=400,
            detail=f"No account connected for {request.platform}"
        )

    try:
        platform = Platform(request.platform)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {request.platform}")

    schedule_time = None
    if request.schedule_time:
        try:
            schedule_time = _dt.fromisoformat(request.schedule_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="schedule_time must be ISO-8601")

    # The service takes a single PublishRequest dataclass (NOT kwargs) and
    # returns a PublishResult — map the HTTP body onto it and translate back.
    job = PublishJob(
        video_path=request.video_path,
        title=request.title,
        description=request.description or "",
        hashtags=request.hashtags or [],
        platform=platform,
        schedule_time=schedule_time,
        privacy=request.visibility,
    )

    result = await service.publish(job)

    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=result.error or f"Publish to {request.platform} failed",
        )

    # GET /publish/{job_id} decodes a "<platform>:<video_id>" token.
    job_id = f"{platform}:{result.video_id}" if result.video_id else str(platform)
    return {
        "job_id": job_id,
        "status": str(result.status),
        "platform": str(platform),
        "url": result.video_url,
    }


@router.get("/publish/{job_id}")
async def get_publish_status(job_id: str):
    """Get status of a publish job."""
    service = SocialPublishService.get_instance()

    status = await service.get_publish_status(job_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return PublishStatusResponse(**status)


@router.get("/platforms/{platform}/requirements")
async def get_platform_requirements(platform: str):
    """Get requirements for a specific platform."""
    requirements = {
        "tiktok": {
            "max_duration": 180,  # 3 minutes
            "aspect_ratios": ["9:16"],
            "max_file_size_mb": 287,
            "formats": ["mp4", "webm"],
            "max_title_length": 150,
            "max_hashtags": 10
        },
        "youtube": {
            "max_duration": 43200,  # 12 hours
            "aspect_ratios": ["16:9", "9:16", "1:1"],
            "max_file_size_mb": 256000,
            "formats": ["mp4", "mov", "avi"],
            "max_title_length": 100,
            "max_description_length": 5000
        },
        "instagram": {
            "max_duration": 90,
            "aspect_ratios": ["9:16", "1:1", "4:5"],
            "max_file_size_mb": 650,
            "formats": ["mp4"],
            "max_caption_length": 2200,
            "max_hashtags": 30
        }
    }

    if platform not in requirements:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown platform: {platform}"
        )

    return requirements[platform]
