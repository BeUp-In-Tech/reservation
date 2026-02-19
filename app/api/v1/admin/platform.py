from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.database import get_db
from app.models import AdminUser, PlatformSettings
from app.api.v1.admin.auth import get_current_admin

router = APIRouter()


class PlatformNameUpdate(BaseModel):
    platform_name: str = Field(..., min_length=1, max_length=200)


class PlatformNameResponse(BaseModel):
    platform_name: str
    updated_at: str | None


@router.get("/platform-name", response_model=PlatformNameResponse)
async def get_platform_name(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get current platform name (admin)."""
    result = await db.execute(
        select(PlatformSettings).where(PlatformSettings.key == "platform_name")
    )
    setting = result.scalar_one_or_none()

    return PlatformNameResponse(
        platform_name=setting.value if setting else "AI Booking System",
        updated_at=setting.updated_at.isoformat() if setting and setting.updated_at else None,
    )


@router.put("/platform-name", response_model=PlatformNameResponse)
async def update_platform_name(
    request: PlatformNameUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Update platform name (admin only)."""
    result = await db.execute(
        select(PlatformSettings).where(PlatformSettings.key == "platform_name")
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = request.platform_name
        setting.updated_at = datetime.utcnow()
    else:
        setting = PlatformSettings(
            key="platform_name",
            value=request.platform_name,
        )
        db.add(setting)

    await db.commit()
    await db.refresh(setting)

    return PlatformNameResponse(
        platform_name=setting.value,
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None,
    )
