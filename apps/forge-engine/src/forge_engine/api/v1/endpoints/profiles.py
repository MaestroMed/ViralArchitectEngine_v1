"""Export profile endpoints."""

import uuid
from datetime import datetime
from forge_engine.core.timeutils import utcnow

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.database import get_db
from forge_engine.models.profile import ExportProfile

router = APIRouter()


class ProfileCreate(BaseModel):
    """Request to create a profile."""
    name: str
    description: str | None = None
    layout_config: dict | None = None
    subtitle_style: dict | None = None
    intro_config: dict | None = None
    music_config: dict | None = None
    export_settings: dict | None = None
    segment_filters: dict | None = None
    is_default: bool = False


class ProfileUpdate(BaseModel):
    """Request to update a profile."""
    name: str | None = None
    description: str | None = None
    layout_config: dict | None = None
    subtitle_style: dict | None = None
    intro_config: dict | None = None
    music_config: dict | None = None
    export_settings: dict | None = None
    segment_filters: dict | None = None
    is_default: bool | None = None


@router.get("")
async def list_profiles(db: AsyncSession = Depends(get_db)) -> dict:
    """List all export profiles."""
    result = await db.execute(
        select(ExportProfile).order_by(ExportProfile.name)
    )
    profiles = result.scalars().all()

    return {
        "success": True,
        "data": [p.to_dict() for p in profiles]
    }


@router.get("/default")
async def get_default_profile(db: AsyncSession = Depends(get_db)) -> dict:
    """Get the default profile."""
    result = await db.execute(
        select(ExportProfile).where(ExportProfile.is_default)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return {"success": True, "data": None}

    return {"success": True, "data": profile.to_dict()}


@router.get("/{profile_id}")
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Get a specific profile."""
    result = await db.execute(
        select(ExportProfile).where(ExportProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {"success": True, "data": profile.to_dict()}


@router.post("")
async def create_profile(request: ProfileCreate, db: AsyncSession = Depends(get_db)) -> dict:
    """Create a new export profile."""
    # If setting as default, unset other defaults
    if request.is_default:
        await db.execute(
            update(ExportProfile).values(is_default=False)
        )

    profile = ExportProfile(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        layout_config=request.layout_config or {},
        subtitle_style=request.subtitle_style or {},
        intro_config=request.intro_config or {},
        music_config=request.music_config or {},
        export_settings=request.export_settings or {},
        segment_filters=request.segment_filters or {},
        is_default=request.is_default,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return {"success": True, "data": profile.to_dict()}


@router.put("/{profile_id}")
async def update_profile(
    profile_id: str,
    request: ProfileUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update an export profile."""
    result = await db.execute(
        select(ExportProfile).where(ExportProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # If setting as default, unset other defaults
    if request.is_default:
        await db.execute(
            update(ExportProfile)
            .where(ExportProfile.id != profile_id)
            .values(is_default=False)
        )

    # Update fields
    if request.name is not None:
        profile.name = request.name
    if request.description is not None:
        profile.description = request.description
    if request.layout_config is not None:
        profile.layout_config = request.layout_config
    if request.subtitle_style is not None:
        profile.subtitle_style = request.subtitle_style
    if request.intro_config is not None:
        profile.intro_config = request.intro_config
    if request.music_config is not None:
        profile.music_config = request.music_config
    if request.export_settings is not None:
        profile.export_settings = request.export_settings
    if request.segment_filters is not None:
        profile.segment_filters = request.segment_filters
    if request.is_default is not None:
        profile.is_default = request.is_default

    profile.updated_at = utcnow()

    await db.commit()
    await db.refresh(profile)

    return {"success": True, "data": profile.to_dict()}


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Delete an export profile."""
    result = await db.execute(
        select(ExportProfile).where(ExportProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    await db.delete(profile)
    await db.commit()

    return {"success": True, "data": {"deleted": True}}


@router.post("/{profile_id}/set-default")
async def set_default_profile(profile_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Set a profile as the default."""
    result = await db.execute(
        select(ExportProfile).where(ExportProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Unset all defaults
    await db.execute(update(ExportProfile).values(is_default=False))

    # Set this one as default
    profile.is_default = True
    await db.commit()

    return {"success": True, "data": profile.to_dict()}