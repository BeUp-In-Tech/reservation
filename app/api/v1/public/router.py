from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, date, timedelta
import uuid

from app.core.database import get_db
from app.models import Business, Service, Booking, BusinessOperatingHours


router = APIRouter()


# ============== Response Models ==============

class ServicePublicResponse(BaseModel):
    id: str
    slug: str
    service_name: str
    description: str | None
    timezone: str
    open_time: str | None
    close_time: str | None


class TimeSlotResponse(BaseModel):
    time: str
    available: bool


class SlotsResponse(BaseModel):
    date: str
    service_id: str
    service_name: str
    duration_minutes: int
    slots: list[TimeSlotResponse]


class BookingPublicResponse(BaseModel):
    tracking_id: str
    status: str
    service_name: str
    slot_start: str | None
    slot_end: str | None
    customer_name: str | None
    created_at: str | None

class BusinessPublicResponse(BaseModel):
    id: str
    business_name: str
    slug: str
    service_name: str | None
    description: str | None
    phone: str | None
    email: str | None
    

# ============== Endpoints ==============

class PlatformNamePublicResponse(BaseModel):
    platform_name: str


@router.get("/platform-name", response_model=PlatformNamePublicResponse)
async def get_platform_name_public(
    db: AsyncSession = Depends(get_db),
):
    """Get platform name (public, no auth)."""
    from app.models import PlatformSettings
    result = await db.execute(
        select(PlatformSettings).where(PlatformSettings.key == "platform_name")
    )
    setting = result.scalar_one_or_none()
    return PlatformNamePublicResponse(
        platform_name=setting.value if setting else "AI Booking System",
    )


@router.get("/{business_slug}", response_model=BusinessPublicResponse)
async def get_business_public(
    business_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Get public business info by slug."""
    result = await db.execute(
        select(Business).where(Business.slug == business_slug, Business.is_active == True)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    return BusinessPublicResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        service_name=business.service_name,
        description=business.description,
        phone=business.phone,
        email=business.email,
        
    )

@router.get("/{business_slug}/services", response_model=list[ServicePublicResponse])
async def get_services_public(
    business_slug: str,
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search by name"),
    popular_only: bool = Query(False, description="Show only popular services"),
    db: AsyncSession = Depends(get_db)
):
    """Get all active services for a business (public, no auth required)."""
    
    # Get business
    result = await db.execute(
        select(Business).where(Business.slug == business_slug, Business.is_active == True)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Build query
    query = select(Service).where(
        Service.business_id == business.id,
        Service.is_active == True
    )
    
    # Apply filters
    if category:
        query = query.where(Service.category == category.upper())
    
    if search:
        query = query.where(Service.service_name.ilike(f"%{search}%"))
    
    if popular_only:
        query = query.where(Service.is_popular == True)
    
    # Order: popular first, then by name
    query = query.order_by(Service.is_popular.desc(), Service.service_name)
    
    result = await db.execute(query)
    services = result.scalars().all()
    
    return [
        ServicePublicResponse(
            id=str(s.id),
            slug=s.slug,
            service_name=s.service_name,
            description=s.description,
            timezone=s.timezone,
            open_time=s.open_time.strftime("%H:%M") if s.open_time else None,
            close_time=s.close_time.strftime("%H:%M") if s.close_time else None,
        )
        for s in services
    ]


@router.get("/{business_slug}/services/{service_id}", response_model=ServicePublicResponse)
async def get_service_detail_public(
    business_slug: str,
    service_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get single service details (public)."""
    
    result = await db.execute(
        select(Service).join(Business).where(
            Business.slug == business_slug,
            Service.id == uuid.UUID(service_id),
            Service.is_active == True
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return ServicePublicResponse(
        id=str(service.id),
        slug=service.slug,
        service_name=service.service_name,
        description=service.description,
        timezone=service.timezone,
        open_time=service.open_time.strftime("%H:%M") if service.open_time else None,
        close_time=service.close_time.strftime("%H:%M") if service.close_time else None,
    )


@router.get("/{business_slug}/slots", response_model=SlotsResponse)
async def get_available_slots(
    business_slug: str,
    service_id: str = Query(..., description="Service ID"),
    date_str: str = Query(..., alias="date", description="Date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db)
):
    """Get available time slots for a service on a specific date."""
    
    # Get business
    result = await db.execute(
        select(Business).where(Business.slug == business_slug)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    # Get service
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(service_id),
            Service.business_id == business.id,
            Service.is_active == True
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Parse date
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get operating hours for that day
    day_of_week = target_date.weekday()  # Monday = 0, Sunday = 6
    
    result = await db.execute(
        select(BusinessOperatingHours).where(
            BusinessOperatingHours.business_id == business.id,
            BusinessOperatingHours.day_of_week == day_of_week
        )
    )
    operating_hours = result.scalar_one_or_none()
    
    # Default hours if not set
    if operating_hours and operating_hours.is_closed:
        return SlotsResponse(
            date=date_str,
            service_id=service_id,
            service_name=service.service_name,
            duration_minutes=service.duration_minutes or 60,
            slots=[]
        )
    
    open_time = operating_hours.open_time if operating_hours else datetime.strptime("09:00", "%H:%M").time()
    close_time = operating_hours.close_time if operating_hours else datetime.strptime("18:00", "%H:%M").time()
    
    # Get existing bookings for that date and service
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    
    result = await db.execute(
        select(Booking).where(
            Booking.service_id == service.id,
            Booking.slot_start >= start_of_day,
            Booking.slot_start <= end_of_day,
            Booking.status.notin_(["CANCELLED", "CANCELED", "FAILED", "EXPIRED"])
        )
    )
    existing_bookings = result.scalars().all()
    booked_times = {b.slot_start.strftime("%H:%M") for b in existing_bookings if b.slot_start}
    
    # Generate time slots
    duration = service.duration_minutes or 60
    slots = []
    
    current_time = datetime.combine(target_date, open_time)
    end_time = datetime.combine(target_date, close_time)
    
    while current_time + timedelta(minutes=duration) <= end_time:
        time_str = current_time.strftime("%H:%M")
        is_available = time_str not in booked_times
        
        # Don't show past slots for today
        if target_date == date.today() and current_time <= datetime.now():
            is_available = False
        
        slots.append(TimeSlotResponse(
            time=current_time.strftime("%I:%M %p"),
            available=is_available
        ))
        
        current_time += timedelta(minutes=duration)
    
    return SlotsResponse(
        date=date_str,
        service_id=service_id,
        service_name=service.service_name,
        duration_minutes=duration,
        slots=slots
    )


@router.get("/bookings/{tracking_id}", response_model=BookingPublicResponse)
async def get_booking_by_tracking_id(
    tracking_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get booking details by tracking ID (public)."""
    
    result = await db.execute(
        select(Booking).where(Booking.public_tracking_id == tracking_id.upper())
    )
    booking = result.scalar_one_or_none()
    
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Get service name
    result = await db.execute(
        select(Service).where(Service.id == booking.service_id)
    )
    service = result.scalar_one_or_none()
    
    return BookingPublicResponse(
        tracking_id=booking.public_tracking_id,
        status=booking.status,
        service_name=service.service_name if service else "Unknown",
        slot_start=booking.slot_start.isoformat() if booking.slot_start else None,
        slot_end=booking.slot_end.isoformat() if booking.slot_end else None,
        customer_name=booking.customer_name,
        created_at=booking.created_at.isoformat() if booking.created_at else None
    )


@router.get("/bookings/my/list", response_model=list[BookingPublicResponse])
async def get_my_bookings(
    phone: str | None = Query(None, description="Phone number"),
    email: str | None = Query(None, description="Email address"),
    db: AsyncSession = Depends(get_db)
):
    """Get all bookings for a customer by phone or email."""
    
    if not phone and not email:
        raise HTTPException(status_code=400, detail="Phone or email is required")
    
    query = select(Booking)
    
    if phone:
        query = query.where(Booking.customer_phone == phone)
    elif email:
        query = query.where(Booking.customer_email == email)
    
    query = query.order_by(Booking.created_at.desc())
    
    result = await db.execute(query)
    bookings = result.scalars().all()
    
    # Get service names
    service_ids = [b.service_id for b in bookings if b.service_id]
    services_dict = {}
    
    if service_ids:
        result = await db.execute(
            select(Service).where(Service.id.in_(service_ids))
        )
        services = result.scalars().all()
        services_dict = {s.id: s.service_name for s in services}
    
    return [
        BookingPublicResponse(
            tracking_id=b.public_tracking_id,
            status=b.status,
            service_name=services_dict.get(b.service_id, "Unknown"),
            slot_start=b.slot_start.isoformat() if b.slot_start else None,
            slot_end=b.slot_end.isoformat() if b.slot_end else None,
            customer_name=b.customer_name,
            created_at=b.created_at.isoformat() if b.created_at else None
        )
        for b in bookings
    ]


@router.get("/{business_slug}/categories", response_model=list[str])
async def get_service_categories(
    business_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all unique service categories for a business."""
    
    result = await db.execute(
        select(Business).where(Business.slug == business_slug)
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    result = await db.execute(
        select(Service.category).where(
            Service.business_id == business.id,
            Service.is_active == True,
            Service.category.isnot(None)
        ).distinct()
    )
    categories = [row[0] for row in result.fetchall() if row[0]]
    
    return categories
@router.get("/", response_model=list[BusinessPublicResponse])
async def list_all_businesses_public(
    db: AsyncSession = Depends(get_db)
):
    """List all active businesses publicly (no auth required)."""
    result = await db.execute(
        select(Business).where(Business.is_active == True).order_by(Business.business_name)
    )
    businesses = result.scalars().all()

    return [
        BusinessPublicResponse(
            id=str(b.id),
            business_name=b.business_name,
            slug=b.slug,
            service_name=b.service_name,
            description=b.description,
            phone=b.phone,
            email=b.email,
        )
        for b in businesses
    ]


@router.post("/book-business")
async def book_business(
    business_slug: str,
    db: AsyncSession = Depends(get_db)
):
    from app.services.chat_service import ChatService
    chat_service = ChatService(db)
    
    try:
        # Start a new conversation with the selected business
        conversation = await chat_service.start_conversation(business_slug)
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))