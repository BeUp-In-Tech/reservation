from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.models.booking import Booking
from app.models.other_models import BookingStatusHistory

async def set_booking_status(
    db: AsyncSession,
    booking: Booking,
    to_status: str,
    *,
    reason: Optional[str] = None,
    note: Optional[str] = None,
    changed_by_admin_id: Optional[str] = None,
    changed_at: Optional[datetime] = None,
) -> bool:
    from_status = booking.status
    if from_status == to_status:
        return False

    booking.status = to_status

    db.add(
        BookingStatusHistory(
            business_id=booking.business_id,
            booking_id=booking.id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            note=note,
            changed_by_admin_id=uuid.UUID(changed_by_admin_id) if changed_by_admin_id else None,

            changed_at=changed_at,
        )
    )
    return True
