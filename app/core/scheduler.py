import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.services.booking_expiry_service import expire_unpaid_bookings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def run_booking_expiry_check():
    """Wrapper to run expiry check with database session"""
    async with AsyncSessionLocal() as db:
        result = await expire_unpaid_bookings(db)
        logger.info(f"Booking expiry result: {result}")

def start_scheduler():
    """Start the background scheduler"""
    # Run every hour
    scheduler.add_job(
        run_booking_expiry_check,
        CronTrigger(minute=0),  # Run at the top of every hour
        id="expire_unpaid_bookings",
        name="Expire unpaid bookings after 24 hours",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Background scheduler started - checking for expired bookings every hour")

def stop_scheduler():
    """Stop the scheduler on shutdown"""
    scheduler.shutdown()
    logger.info("Background scheduler stopped")
