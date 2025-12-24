"""Profile endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.database import get_db
from forge_engine.models import Profile

router = APIRouter()


class CreateProfileRequest(BaseModel):
    name: str
    description: Optional[str] = None
    custom_dictionary: list[str] = []
    preferred_caption_style: Optional[str] = None
    preferred_layout: Optional[str] = None
    target_duration: dict = {"min": 15, "max": 60, "optimal": 30}
    hook_patterns: Optional[list[str]] = None
    content_tags: Optional[list[str]] = None
    is_default: bool = False


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    custom_dictionary: Optional[list[str]] = None
    preferred_caption_style: Optional[str] = None
    preferred_layout: Optional[str] = None
    target_duration: Optional[dict] = None
    hook_patterns: Optional[list[str]] = None
    content_tags: Optional[list[str]] = None
    is_default: Optional[bool] = None


@router.post("")
async def create_profile(
    request: CreateProfileRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Create a new profile."""
    profile = Profile(
        name=request.name,
        description=request.description,
        custom_dictionary=request.custom_dictionary,
        preferred_caption_style=request.preferred_caption_style,
        preferred_layout=request.preferred_layout,
        target_duration=request.target_duration,
        hook_patterns=request.hook_patterns,
        content_tags=request.content_tags,
        is_default=request.is_default,
    )
    
    # If this is default, unset other defaults
    if request.is_default:
        await db.execute(
            Profile.__table__.update().values(is_default=False)
        )
    
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    
    return {"success": True, "data": profile.to_dict()}


@router.get("")
async def list_profiles(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List all profiles."""
    result = await db.execute(select(Profile).order_by(Profile.name))
    profiles = result.scalars().all()
    
    return {"success": True, "data": [p.to_dict() for p in profiles]}


@router.get("/{profile_id}")
async def get_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a profile by ID."""
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"success": True, "data": profile.to_dict()}


@router.put("/{profile_id}")
async def update_profile(
    profile_id: str,
    request: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update a profile."""
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Update fields
    if request.name is not None:
        profile.name = request.name
    if request.description is not None:
        profile.description = request.description
    if request.custom_dictionary is not None:
        profile.custom_dictionary = request.custom_dictionary
    if request.preferred_caption_style is not None:
        profile.preferred_caption_style = request.preferred_caption_style
    if request.preferred_layout is not None:
        profile.preferred_layout = request.preferred_layout
    if request.target_duration is not None:
        profile.target_duration = request.target_duration
    if request.hook_patterns is not None:
        profile.hook_patterns = request.hook_patterns
    if request.content_tags is not None:
        profile.content_tags = request.content_tags
    if request.is_default is not None:
        if request.is_default:
            await db.execute(
                Profile.__table__.update().values(is_default=False)
            )
        profile.is_default = request.is_default
    
    await db.commit()
    await db.refresh(profile)
    
    return {"success": True, "data": profile.to_dict()}


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete a profile."""
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    await db.delete(profile)
    await db.commit()
    
    return {"success": True, "data": {"deleted": True}}









