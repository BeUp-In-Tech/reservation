from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, time
from typing import Optional, Literal, List
import uuid

from app.core.database import get_db
from app.models.business import Business
from app.models.other_models import BusinessAISettings, AdminUser, BusinessOperatingHours
from app.models.business_profile import BusinessProfile
from app.models.business_address import BusinessAddress
from app.api.v1.admin.auth import get_current_admin

router = APIRouter()

ALLOWED_INDUSTRIES = {"HOTEL", "RESTAURANT", "SALON", "CLINIC", "OTHER", "SPA"}


def map_industry(value: str | None) -> tuple[str, str | None]:
    if not value:
        return "OTHER", None
    label = value.strip().upper()
    if label in ALLOWED_INDUSTRIES:
        return label, label
    return "OTHER", label


# ============== Request/Response Models ==============

class BusinessCreate(BaseModel):
    business_name: str
    slug: str
    industry: str = "HOTEL"
    timezone: str = "Asia/Dhaka"


class BusinessUpdate(BaseModel):
    business_name: str | None = None
    timezone: str | None = None
    status: str | None = None


class BusinessResponse(BaseModel):
    id: str
    business_name: str
    slug: str
    industry: str
    industry_label: str | None = None
    timezone: str
    status: str | None
    created_at: str | None


class AISettingsUpdate(BaseModel):
    agent_name: str | None = None
    tone_of_voice: str | None = None
    welcome_message: str | None = None
    fallback_message: str | None = None
    escalation_message: str | None = None
    max_retries: int | None = None
    language: str | None = None
    min_notice_hours: int | None = None
    max_per_slot: int | None = None
    cancellation_policy: str | None = None


class AISettingsResponse(BaseModel):
    id: str
    business_id: str
    agent_name: str
    tone_of_voice: str | None
    welcome_message: str | None
    fallback_message: str | None
    escalation_message: str | None
    max_retries: int | None
    language: str | None
    min_notice_hours: int | None
    max_per_slot: int | None
    cancellation_policy: str | None


# ============== Helper ==============

async def _get_business_or_404(db: AsyncSession, business_id: str) -> Business:
    try:
        bid = uuid.UUID(business_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid business_id")
    result = await db.execute(select(Business).where(Business.id == bid))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


# ============== Business Endpoints ==============

@router.get("/", response_model=list[BusinessResponse])
async def list_businesses(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(Business).order_by(Business.created_at.desc()))
    businesses = result.scalars().all()
    return [
        BusinessResponse(
            id=str(b.id),
            business_name=b.business_name,
            slug=b.slug,
            industry=b.industry,
            industry_label=b.industry_label,
            timezone=b.timezone,
            status=b.status,
            created_at=b.created_at.isoformat() if b.created_at else None,
        )
        for b in businesses
    ]


@router.post("/", response_model=BusinessResponse)
async def create_business(
    request: BusinessCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(Business).where(Business.slug == request.slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    enum_industry, industry_label = map_industry(request.industry)

    business = Business(
        business_name=request.business_name,
        slug=request.slug,
        industry=enum_industry,
        industry_label=industry_label,
        timezone=request.timezone,
        status="ACTIVE",
        created_by_admin_id=current_admin.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(business)
    await db.flush()

    # Create default AI settings
    ai_settings = BusinessAISettings(
        business_id=business.id,
        agent_name="Assistant",
        tone_of_voice="friendly and professional",
        welcome_message="Hello! How can I help you today?",
        fallback_message="I'm sorry, I didn't understand that.",
        escalation_message="I'll connect you with a human representative.",
        max_retries=3,
        language="en",
    )
    db.add(ai_settings)

    # Create default operating hours (Mon-Sun 9AM-6PM)
    for day in range(7):
        hours = BusinessOperatingHours(
            id=uuid.uuid4(),
            business_id=business.id,
            day_of_week=day,
            open_time=time(9, 0),
            close_time=time(18, 0),
            is_closed=False,
        )
        db.add(hours)

    await db.commit()
    await db.refresh(business)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)
    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: str,
    request: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    if request.business_name is not None:
        business.business_name = request.business_name
    if request.timezone is not None:
        business.timezone = request.timezone
    if request.status is not None:
        business.status = request.status

    business.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(business)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )


# ============== AI Settings Endpoints ==============

@router.get("/{business_id}/ai-settings", response_model=AISettingsResponse)
async def get_ai_settings(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(BusinessAISettings).where(BusinessAISettings.business_id == uuid.UUID(business_id))
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="AI settings not found")

    return AISettingsResponse(
        id=str(settings.id),
        business_id=str(settings.business_id),
        agent_name=settings.agent_name,
        tone_of_voice=settings.tone_of_voice,
        welcome_message=settings.welcome_message,
        fallback_message=settings.fallback_message,
        escalation_message=settings.escalation_message,
        max_retries=settings.max_retries,
        language=settings.language,
        min_notice_hours=settings.min_notice_hours,
        max_per_slot=settings.max_per_slot,
        cancellation_policy=settings.cancellation_policy,
    )


@router.patch("/{business_id}/ai-settings", response_model=AISettingsResponse)
async def update_ai_settings(
    business_id: str,
    request: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(BusinessAISettings).where(BusinessAISettings.business_id == uuid.UUID(business_id))
    )
    settings = result.scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=404, detail="AI settings not found")

    if request.agent_name is not None:
        settings.agent_name = request.agent_name
    if request.tone_of_voice is not None:
        settings.tone_of_voice = request.tone_of_voice
    if request.welcome_message is not None:
        settings.welcome_message = request.welcome_message
    if request.fallback_message is not None:
        settings.fallback_message = request.fallback_message
    if request.escalation_message is not None:
        settings.escalation_message = request.escalation_message
    if request.max_retries is not None:
        settings.max_retries = request.max_retries
    if request.language is not None:
        settings.language = request.language
    if request.min_notice_hours is not None:
        settings.min_notice_hours = request.min_notice_hours
    if request.max_per_slot is not None:
        settings.max_per_slot = request.max_per_slot
    if request.cancellation_policy is not None:
        settings.cancellation_policy = request.cancellation_policy

    settings.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(settings)

    return AISettingsResponse(
        id=str(settings.id),
        business_id=str(settings.business_id),
        agent_name=settings.agent_name,
        tone_of_voice=settings.tone_of_voice,
        welcome_message=settings.welcome_message,
        fallback_message=settings.fallback_message,
        escalation_message=settings.escalation_message,
        max_retries=settings.max_retries,
        language=settings.language,
        min_notice_hours=settings.min_notice_hours,
        max_per_slot=settings.max_per_slot,
        cancellation_policy=settings.cancellation_policy,
    )
