from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.database import get_db
from app.models import AdminUser, PlatformSettings
from app.api.v1.admin.auth import get_current_admin

router = APIRouter()


# ============== Platform Name ==============

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


# ============== Platform Contact Info ==============

class PlatformContactUpdate(BaseModel):
    contact_phone: str | None = Field(None, max_length=40)
    contact_email: str | None = Field(None, max_length=255)
    contact_address: str | None = Field(None, max_length=500)


class PlatformContactResponse(BaseModel):
    contact_phone: str | None
    contact_email: str | None
    contact_address: str | None
    updated_at: str | None


CONTACT_KEYS = ["contact_phone", "contact_email", "contact_address"]


async def _get_contact_settings(db: AsyncSession) -> dict:
    """Read contact_phone, contact_email, contact_address from platform_settings."""
    result = await db.execute(
        select(PlatformSettings).where(PlatformSettings.key.in_(CONTACT_KEYS))
    )
    settings = result.scalars().all()
    data = {s.key: s.value for s in settings}
    latest_update = None
    for s in settings:
        if s.updated_at:
            if latest_update is None:
                latest_update = s.updated_at
            elif s.updated_at.replace(tzinfo=None) > latest_update.replace(tzinfo=None):
                latest_update = s.updated_at
    return {
        "contact_phone": data.get("contact_phone"),
        "contact_email": data.get("contact_email"),
        "contact_address": data.get("contact_address"),
        "updated_at": latest_update.isoformat() if latest_update else None,
    }


@router.get("/platform-contact", response_model=PlatformContactResponse)
async def get_platform_contact(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get platform contact info (admin)."""
    return PlatformContactResponse(**await _get_contact_settings(db))


@router.put("/platform-contact", response_model=PlatformContactResponse)
async def update_platform_contact(
    request: PlatformContactUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Update platform contact info (admin only). Shown on public Contact Us page."""
    updates = {
        "contact_phone": request.contact_phone,
        "contact_email": request.contact_email,
        "contact_address": request.contact_address,
    }

    for key, value in updates.items():
        result = await db.execute(
            select(PlatformSettings).where(PlatformSettings.key == key)
        )
        setting = result.scalar_one_or_none()

        if value is not None:
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = PlatformSettings(key=key, value=value)
                db.add(setting)
        elif setting:
            # If value is None, clear it
            setting.value = ""
            setting.updated_at = datetime.utcnow()

    await db.commit()

    return PlatformContactResponse(**await _get_contact_settings(db))