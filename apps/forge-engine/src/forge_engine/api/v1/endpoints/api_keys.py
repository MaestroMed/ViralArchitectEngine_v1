"""API key management endpoints.

These routes are protected by `require_api_key` like the rest of /v1 — once
auth is enabled you need an existing key to mint a new one. Bootstrap via
the CLI: `python -m forge_engine.scripts.seed_api_key create "iPhone"`.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from forge_engine.core.database import async_session_maker
from forge_engine.models.api_key import ApiKey, generate_key, hash_key

router = APIRouter()


class CreateApiKeyRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)


class CreatedApiKeyResponse(BaseModel):
    """Includes the raw `key` field — shown exactly ONCE at creation."""
    id: str
    label: str
    key: str
    createdAt: str


@router.get("")
async def list_api_keys() -> dict:
    """List all non-revoked keys. The raw secret is never returned."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(ApiKey).where(ApiKey.revoked_at.is_(None)).order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()
        return {"success": True, "data": [k.to_dict() for k in keys]}


@router.post("", status_code=201)
async def create_api_key(request: CreateApiKeyRequest) -> CreatedApiKeyResponse:
    """Mint a new key. The raw value is in the response — store it now, it
    won't be retrievable afterwards."""
    raw = generate_key()
    row = ApiKey(label=request.label, key_hash=hash_key(raw))
    async with async_session_maker() as db:
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return CreatedApiKeyResponse(
        id=row.id,
        label=row.label,
        key=raw,
        createdAt=row.created_at.isoformat(),
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(key_id: str) -> None:
    """Revoke a key. Future requests with it return 401. The row is kept for
    audit (last_used_at is still readable in the database)."""
    async with async_session_maker() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
        row = result.scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            raise HTTPException(status_code=404, detail="Key not found")
        await db.execute(
            update(ApiKey).where(ApiKey.id == key_id).values(revoked_at=datetime.utcnow())
        )
        await db.commit()
