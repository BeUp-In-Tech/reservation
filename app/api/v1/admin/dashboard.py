from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models import Booking, CallSession, AdminUser
from app.api.v1.admin.auth import get_current_admin

router = APIRouter()


# ============== Models ==============

class RecentBooking(BaseModel):
    id: str
    public_tracking_id: str
    customer_name: str | None
    customer_phone: str | None
    status: str
    created_at: str | None


class DashboardResponse(BaseModel):
    total_bookings: int
    total_calls: int
    recent_bookings: list[RecentBooking]


# ============== Dashboard Endpoint ==============

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get dashboard stats: total bookings, total calls, recent bookings."""
    
    # Total bookings count
    bookings_result = await db.execute(select(func.count(Booking.id)))
    total_bookings = bookings_result.scalar() or 0

    # Total calls count
    calls_result = await db.execute(select(func.count(CallSession.id)))
    total_calls = calls_result.scalar() or 0

    # Recent 10 bookings
    recent_result = await db.execute(
        select(Booking)
        .order_by(Booking.created_at.desc())
        .limit(10)
    )
    recent_bookings_list = recent_result.scalars().all()

    recent_bookings = [
        RecentBooking(
            id=str(b.id),
            public_tracking_id=b.public_tracking_id,
            customer_name=b.customer_name,
            customer_phone=b.customer_phone,
            status=b.status,
            created_at=b.created_at.isoformat() if b.created_at else None,
        )
        for b in recent_bookings_list
    ]

    return DashboardResponse(
        total_bookings=total_bookings,
        total_calls=total_calls,
        recent_bookings=recent_bookings,
    )
@router.post("/test-expire-bookings")
async def test_expire_bookings(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Manual trigger for testing booking expiry"""
    from app.services.booking_expiry_service import expire_unpaid_bookings
    result = await expire_unpaid_bookings(db)
    return result