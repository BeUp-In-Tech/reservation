from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, Field
from datetime import datetime, time
from typing import List
import uuid

from app.core.database import get_db
from app.models.business import Business
from app.models.other_models import BusinessOperatingHours, BusinessAISettings, AdminUser

from app.api.v1.admin.auth import get_current_admin

router = APIRouter()


# ============== Models ==============

class DayHours(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    is_closed: bool = False
    open_time: str | None = None
    close_time: str | None = None


class WeeklyHours(BaseModel):
    days: List[DayHours] = Field(..., min_length=7, max_length=7)


class BusinessCreate(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=120)
    timezone: str = Field(..., min_length=1, max_length=64)
    weekly_hours: WeeklyHours
    description: str = Field(..., min_length=1)
    service_type_name: str = Field(..., min_length=1, max_length=120)
    contact_fullname: str = Field(..., min_length=1, max_length=120)
    contact_email: str = Field(..., min_length=1, max_length=255)
    contact_phone: str = Field(..., min_length=1, max_length=40)
    street_address: str = Field(..., min_length=1)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)
    zip_code: str = Field(..., min_length=1, max_length=30)
    country: str = Field(..., min_length=1, max_length=100)
    default_currency: str = "BDT"


class BusinessUpdate(BaseModel):
    business_name: str | None = None
    description: str | None = None
    service_type_name: str | None = None
    contact_fullname: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    timezone: str | None = None


class BusinessResponse(BaseModel):
    id: str
    business_name: str
    slug: str
    description: str | None = None
    service_type_name: str | None = None
    contact_fullname: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None
    timezone: str
    default_currency: str | None = None
    status: str
    is_active: bool
    created_at: str | None
    service_count: int = 0


class DeleteResponse(BaseModel):
    success: bool
    message: str


class AISettingsUpdate(BaseModel):
    agent_name: str | None = None
    tone_of_voice: str | None = None
    welcome_message: str | None = None
    fallback_message: str | None = None
    escalation_message: str | None = None
    max_retries: int | None = None
    language: str | None = None


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


# ============== Helpers ==============

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


async def _get_service_count(db: AsyncSession, business_id: uuid.UUID) -> int:
    from app.models import Service
    result = await db.execute(
        select(Service).where(Service.business_id == business_id, Service.is_active == True)
    )
    return len(result.scalars().all())


def _parse_time(time_str: str) -> time:
    h, m = map(int, time_str.split(":"))
    return time(h, m)


# ============== Business Endpoints ==============

@router.get("/", response_model=List[BusinessResponse])
async def list_businesses(
    name: str | None = Query(None, description="Filter by business name"),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """List all businesses."""
    query = select(Business).order_by(Business.created_at.desc())
    if name:
        query = query.where(Business.business_name.ilike(f"%{name}%"))

    result = await db.execute(query)
    businesses = result.scalars().all()

    responses = []
    for b in businesses:
        service_count = await _get_service_count(db, b.id)
        responses.append(BusinessResponse(
            id=str(b.id),
            business_name=b.business_name,
            slug=b.slug,
            description=b.description,
            service_type_name=b.service_type_name,
            contact_fullname=b.contact_person,
            contact_email=b.email,
            contact_phone=b.phone,
            street_address=b.street_address,
            city=b.city,
            state=b.state,
            zip_code=b.zip_code,
            country=b.country,
            timezone=b.timezone,
            default_currency=b.default_currency,
            status=b.status,
            is_active=b.is_active,
            created_at=b.created_at.isoformat() if b.created_at else None,
            service_count=service_count,
        ))
    return responses


@router.post("/", response_model=BusinessResponse)
async def create_business(
    request: BusinessCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Create a new business with all info at once."""
    
    # Check slug
    result = await db.execute(select(Business).where(Business.slug == request.slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    # Validate hours
    for d in request.weekly_hours.days:
        if not d.is_closed and (not d.open_time or not d.close_time):
            raise HTTPException(status_code=400, detail=f"Day {d.day_of_week}: times required when not closed")

    # Create business
    business = Business(
        business_name=request.business_name,
        slug=request.slug,
        description=request.description,
        service_type_name=request.service_type_name,
        contact_person=request.contact_fullname,
        email=request.contact_email,
        phone=request.contact_phone,
        street_address=request.street_address,
        city=request.city,
        state=request.state,
        zip_code=request.zip_code,
        country=request.country,
        timezone=request.timezone,
        default_currency=request.default_currency,
        status="ACTIVE",
        is_active=True,
        created_by_admin_id=current_admin.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(business)
    await db.flush()

    # Create operating hours
    for d in request.weekly_hours.days:
        ot = _parse_time(d.open_time) if not d.is_closed else None
        ct = _parse_time(d.close_time) if not d.is_closed else None
        db.add(BusinessOperatingHours(
            business_id=business.id,
            day_of_week=d.day_of_week,
            open_time=ot,
            close_time=ct,
            is_closed=d.is_closed,
        ))

    # Create AI settings
    db.add(BusinessAISettings(
        business_id=business.id,
        agent_name="Assistant",
        tone_of_voice="friendly and professional",
        welcome_message="Hello! How can I help you today?",
        fallback_message="I'm sorry, I didn't understand that.",
        escalation_message="I'll connect you with a human representative.",
        max_retries=3,
        language="en",
    ))

    await db.commit()
    await db.refresh(business)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        description=business.description,
        service_type_name=business.service_type_name,
        contact_fullname=business.contact_person,
        contact_email=business.email,
        contact_phone=business.phone,
        street_address=business.street_address,
        city=business.city,
        state=business.state,
        zip_code=business.zip_code,
        country=business.country,
        timezone=business.timezone,
        default_currency=business.default_currency,
        status=business.status,
        is_active=business.is_active,
        created_at=business.created_at.isoformat() if business.created_at else None,
        service_count=0,
    )


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get a business by ID."""
    business = await _get_business_or_404(db, business_id)
    service_count = await _get_service_count(db, business.id)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        description=business.description,
        service_type_name=business.service_type_name,
        contact_fullname=business.contact_person,
        contact_email=business.email,
        contact_phone=business.phone,
        street_address=business.street_address,
        city=business.city,
        state=business.state,
        zip_code=business.zip_code,
        country=business.country,
        timezone=business.timezone,
        default_currency=business.default_currency,
        status=business.status,
        is_active=business.is_active,
        created_at=business.created_at.isoformat() if business.created_at else None,
        service_count=service_count,
    )


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: str,
    request: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Update a business."""
    business = await _get_business_or_404(db, business_id)

    if request.business_name is not None:
        business.business_name = request.business_name
    if request.description is not None:
        business.description = request.description
    if request.service_type_name is not None:
        business.service_type_name = request.service_type_name
    if request.contact_fullname is not None:
        business.contact_person = request.contact_fullname
    if request.contact_email is not None:
        business.email = request.contact_email
    if request.contact_phone is not None:
        business.phone = request.contact_phone
    if request.street_address is not None:
        business.street_address = request.street_address
    if request.city is not None:
        business.city = request.city
    if request.state is not None:
        business.state = request.state
    if request.zip_code is not None:
        business.zip_code = request.zip_code
    if request.country is not None:
        business.country = request.country
    if request.timezone is not None:
        business.timezone = request.timezone

    business.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(business)

    service_count = await _get_service_count(db, business.id)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        description=business.description,
        service_type_name=business.service_type_name,
        contact_fullname=business.contact_person,
        contact_email=business.email,
        contact_phone=business.phone,
        street_address=business.street_address,
        city=business.city,
        state=business.state,
        zip_code=business.zip_code,
        country=business.country,
        timezone=business.timezone,
        default_currency=business.default_currency,
        status=business.status,
        is_active=business.is_active,
        created_at=business.created_at.isoformat() if business.created_at else None,
        service_count=service_count,
    )


@router.delete("/{business_id}", response_model=DeleteResponse)
async def delete_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """
    Delete a business and ALL related data permanently.
    Frontend should show "Are you sure?" popup before calling this.
    """
    from app.models import Booking, Conversation, Service, CallSession
    from app.models.other_models import (
        BusinessOperatingHours,
        BusinessAISettings,
        BusinessNotificationSettings,
        ServiceImage,
        ServiceCapacityRule,
        BusinessAvailabilityException,
        HandoffRequest,
        PaymentSession,
        BookingStatusHistory,
    )
    from sqlalchemy import text

    business = await _get_business_or_404(db, business_id)
    bid = business.id
    slug = business.slug

    try:
        # 1. Get service IDs
        services_result = await db.execute(select(Service.id).where(Service.business_id == bid))
        service_ids = [row[0] for row in services_result.fetchall()]

        # 2. Delete service-related
        if service_ids:
            await db.execute(delete(ServiceImage).where(ServiceImage.service_id.in_(service_ids)))
            await db.execute(delete(ServiceCapacityRule).where(ServiceCapacityRule.service_id.in_(service_ids)))

        # 3. Get booking IDs
        bookings_result = await db.execute(select(Booking.id).where(Booking.business_id == bid))
        booking_ids = [row[0] for row in bookings_result.fetchall()]

        # 4. Delete booking-related
        if booking_ids:
            await db.execute(delete(BookingStatusHistory).where(BookingStatusHistory.booking_id.in_(booking_ids)))
            await db.execute(delete(PaymentSession).where(PaymentSession.booking_id.in_(booking_ids)))

        # 5. Delete handoffs
        await db.execute(delete(HandoffRequest).where(HandoffRequest.business_id == bid))

        # 6. Delete bookings
        await db.execute(delete(Booking).where(Booking.business_id == bid))

        # 7. Delete call sessions
        await db.execute(delete(CallSession).where(CallSession.business_id == bid))

        # 8. Get conversation IDs and delete messages
        conversations_result = await db.execute(select(Conversation.id).where(Conversation.business_id == bid))
        conversation_ids = [row[0] for row in conversations_result.fetchall()]
        if conversation_ids:
            await db.execute(text("DELETE FROM core.conversation_messages WHERE conversation_id = ANY(:ids)"), {"ids": conversation_ids})

        # 9. Delete conversations
        await db.execute(delete(Conversation).where(Conversation.business_id == bid))

        # 10. Delete operating hours
        await db.execute(delete(BusinessOperatingHours).where(BusinessOperatingHours.business_id == bid))

        # 11. Delete AI settings
        await db.execute(delete(BusinessAISettings).where(BusinessAISettings.business_id == bid))

        # 12. Delete notification settings
        await db.execute(delete(BusinessNotificationSettings).where(BusinessNotificationSettings.business_id == bid))

        # 13. Delete availability exceptions
        await db.execute(delete(BusinessAvailabilityException).where(BusinessAvailabilityException.business_id == bid))

        # 14. Delete admin access
        await db.execute(text("DELETE FROM core.admin_business_access WHERE business_id = :bid"), {"bid": str(bid)})

        # 15. Delete profiles
        await db.execute(text("DELETE FROM core.business_profiles WHERE business_id = :bid"), {"bid": str(bid)})

        # 16. Delete addresses
        await db.execute(text("DELETE FROM core.business_addresses WHERE business_id = :bid"), {"bid": str(bid)})

        # 17. Delete business (services & service_contacts cascade)
        await db.delete(business)

        await db.commit()

        return DeleteResponse(success=True, message=f"Business '{slug}' deleted successfully")

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")


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
    )
