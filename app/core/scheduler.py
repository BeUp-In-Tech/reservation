import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.database import AsyncSessionLocal
from app.services.booking_expiry_service import expire_unpaid_bookings
from app.services.review_reminder_service import send_review_reminders

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def run_booking_expiry_check():
    """Wrapper to run expiry check with database session"""
    async with AsyncSessionLocal() as db:
        result = await expire_unpaid_bookings(db)
        logger.info(f"Booking expiry result: {result}")

async def run_review_reminder_check():
    """Send review reminder emails for bookings approaching the 72h deadline."""
    async with AsyncSessionLocal() as db:
        result = await send_review_reminders(db)
        logger.info(f"Review reminder result: {result}")

def start_scheduler():
    """Start the background scheduler"""
    scheduler.add_job(
        run_booking_expiry_check,
        CronTrigger(minute=0),
        id="expire_unpaid_bookings",
        name="Expire unpaid bookings after 24 hours",
        replace_existing=True
    )
    scheduler.add_job(
        run_review_reminder_check,
        CronTrigger(minute=30),
        id="send_review_reminders",
        name="Send review reminder emails 12h before 72h deadline",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Background scheduler started — booking expiry + review reminders")

def stop_scheduler():
    """Stop the scheduler on shutdown"""
    scheduler.shutdown()
    logger.info("Background scheduler stopped")