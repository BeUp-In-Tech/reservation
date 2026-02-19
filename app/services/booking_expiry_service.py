import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Booking
from app.services.booking_status_history_service import set_booking_status

logger = logging.getLogger(__name__)

async def expire_unpaid_bookings(db: AsyncSession) -> dict:
    """
    Find and expire bookings in PENDING_PAYMENT status older than 24 hours.
    Runs every hour.
    """
    try:
        # Calculate cutoff time (24 hours ago)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Find bookings that are PENDING_PAYMENT and older than 24 hours
        result = await db.execute(
            select(Booking).where(
                Booking.status == "PENDING_PAYMENT",
                Booking.payment_status.in_(["PENDING", "CREATED"]),
                Booking.updated_at < cutoff_time
            )
        )
        expired_bookings = result.scalars().all()
        
        expired_count = 0
        for booking in expired_bookings:
            # Mark as EXPIRED
            await set_booking_status(
                db,
                booking,
                "EXPIRED",
                reason="auto_expiry",
                note=f"Auto-expired after 24 hours without payment"
            )
            booking.payment_status = "EXPIRED"
            booking.updated_at = datetime.utcnow()
            expired_count += 1
            
            logger.info(f"Expired booking {booking.public_tracking_id} - no payment after 24h")
        
        await db.commit()
        
        logger.info(f"Booking expiry check complete: {expired_count} bookings expired")
        
        return {
            "status": "success",
            "expired_count": expired_count,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in expire_unpaid_bookings: {e}")
        await db.rollback()
        return {
            "status": "error",
            "error": str(e)
        }