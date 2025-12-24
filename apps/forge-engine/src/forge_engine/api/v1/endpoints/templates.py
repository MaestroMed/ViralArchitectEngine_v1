"""Template endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge_engine.core.database import get_db
from forge_engine.models import Template

router = APIRouter()


class CreateTemplateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    caption_style: dict
    layout: dict
    hook_card_style: Optional[dict] = None
    brand_kit: Optional[dict] = None
    is_default: bool = False


class UpdateTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    caption_style: Optional[dict] = None
    layout: Optional[dict] = None
    hook_card_style: Optional[dict] = None
    brand_kit: Optional[dict] = None
    is_default: Optional[bool] = None


@router.post("")
async def create_template(
    request: CreateTemplateRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Create a new template."""
    template = Template(
        name=request.name,
        description=request.description,
        caption_style=request.caption_style,
        layout=request.layout,
        hook_card_style=request.hook_card_style,
        brand_kit=request.brand_kit,
        is_default=request.is_default,
    )
    
    # If this is default, unset other defaults
    if request.is_default:
        await db.execute(
            Template.__table__.update().values(is_default=False)
        )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return {"success": True, "data": template.to_dict()}


@router.get("")
async def list_templates(
    db: AsyncSession = Depends(get_db)
) -> dict:
    """List all templates."""
    result = await db.execute(select(Template).order_by(Template.name))
    templates = result.scalars().all()
    
    return {"success": True, "data": [t.to_dict() for t in templates]}


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get a template by ID."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"success": True, "data": template.to_dict()}


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Update a template."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Update fields
    if request.name is not None:
        template.name = request.name
    if request.description is not None:
        template.description = request.description
    if request.caption_style is not None:
        template.caption_style = request.caption_style
    if request.layout is not None:
        template.layout = request.layout
    if request.hook_card_style is not None:
        template.hook_card_style = request.hook_card_style
    if request.brand_kit is not None:
        template.brand_kit = request.brand_kit
    if request.is_default is not None:
        if request.is_default:
            await db.execute(
                Template.__table__.update().values(is_default=False)
            )
        template.is_default = request.is_default
    
    await db.commit()
    await db.refresh(template)
    
    return {"success": True, "data": template.to_dict()}


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Delete a template."""
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.delete(template)
    await db.commit()
    
    return {"success": True, "data": {"deleted": True}}









