from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from app.core.database import get_db
from app.models import Booking, Service, AdminUser
from app.api.v1.admin.auth import get_current_admin

router = APIRouter()


class BookingDetail(BaseModel):
    booking_id: str
    public_tracking_id: str
    customer_name: str | None
    customer_phone: str | None
    customer_email: str | None
    service_name: str | None
    slot_start: str | None
    status: str
    payment_status: str
    created_at: str | None


class BookingSummaryResponse(BaseModel):
    total_bookings: int
    pending_payment: int
    confirmed: int
    cancelled: int
    expired: int
    bookings: list[BookingDetail]


@router.get("/bookings-summary", response_model=BookingSummaryResponse)
async def get_bookings_summary(
    status_filter: str | None = Query(None, description="Filter by status: PENDING_PAYMENT, CONFIRMED, CANCELLED, EXPIRED"),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get total bookings, pending payment count, and all booking details."""

    # Counts
    total = (await db.execute(select(func.count(Booking.id)))).scalar() or 0
    pending = (await db.execute(select(func.count(Booking.id)).where(Booking.status == "PENDING_PAYMENT"))).scalar() or 0
    confirmed = (await db.execute(select(func.count(Booking.id)).where(Booking.status == "CONFIRMED"))).scalar() or 0
    cancelled = (await db.execute(select(func.count(Booking.id)).where(Booking.status.in_(["CANCELLED", "CANCELED"])))).scalar() or 0
    expired = (await db.execute(select(func.count(Booking.id)).where(Booking.status == "EXPIRED"))).scalar() or 0

    # Bookings query with service join
    query = (
        select(Booking, Service.service_name)
        .outerjoin(Service, Booking.service_id == Service.id)
    )

    if status_filter:
        query = query.where(Booking.status == status_filter)

    query = query.order_by(Booking.created_at.desc())

    rows = (await db.execute(query)).all()

    bookings = [
        BookingDetail(
            booking_id=str(b.id),
            public_tracking_id=b.public_tracking_id,
            customer_name=b.customer_name,
            customer_phone=b.customer_phone,
            customer_email=b.customer_email,
            service_name=svc_name,
            slot_start=b.slot_start.isoformat() if b.slot_start else None,
            status=b.status,
            payment_status=b.payment_status,
            created_at=b.created_at.isoformat() if b.created_at else None,
        )
        for b, svc_name in rows
    ]

    return BookingSummaryResponse(
        total_bookings=total,
        pending_payment=pending,
        confirmed=confirmed,
        cancelled=cancelled,
        expired=expired,
        bookings=bookings,
    )
