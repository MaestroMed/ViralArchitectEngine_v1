"""Device (push) registration endpoints.

The iOS app POSTs its APNs device token here once Apple hands it back. We upsert
on the token (re-registering the same device bumps last_seen_at instead of
duplicating). Gated by the same `require_api_key` the rest of /v1 uses (the
dependency is applied at router include time in main.py).
"""

from datetime import datetime
from forge_engine.core.timeutils import utcnow

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from forge_engine.core.database import async_session_maker
from forge_engine.models.device_token import DeviceToken

router = APIRouter()


class RegisterDeviceRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    platform: str = Field(default="ios", max_length=20)
    bundleId: str = Field(..., min_length=1, max_length=200)


@router.post("/register", status_code=200)
async def register_device(request: RegisterDeviceRequest) -> dict:
    """Upsert a push device token. Idempotent on `token`."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(DeviceToken).where(DeviceToken.token == request.token)
        )
        row = result.scalar_one_or_none()
        now = utcnow()
        if row is None:
            row = DeviceToken(
                token=request.token,
                platform=request.platform or "ios",
                bundle_id=request.bundleId,
                created_at=now,
                last_seen_at=now,
            )
            db.add(row)
        else:
            row.platform = request.platform or row.platform
            row.bundle_id = request.bundleId or row.bundle_id
            row.last_seen_at = now
        await db.commit()
        await db.refresh(row)
        return {"success": True, "data": row.to_dict()}