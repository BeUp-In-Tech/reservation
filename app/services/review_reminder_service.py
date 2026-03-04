"""
Review reminder scheduler.
Sends reminder emails 12 hours before the 72-hour review window expires.
"""

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.booking import Booking
from app.models.review import Review
from app.models.service import Service
from app.models.business import Business
from app.core.email import send_email
from app.services.review_service import REVIEW_WINDOW_HOURS

logger = logging.getLogger(__name__)

# Reminder is sent at the 60-hour mark (12 hours before the 72-hour deadline)
REMINDER_AT_HOURS = REVIEW_WINDOW_HOURS - 12  # 60


async def send_review_reminders(db: AsyncSession) -> dict:
    """
    Find confirmed bookings that:
    1. Were confirmed between 60-61 hours ago (so we catch them once per hourly run)
    2. Have no review yet
    3. Have not already received a reminder
    4. Have a customer email

    Send a reminder email to each.
    """
    now = datetime.now(timezone.utc)

    # Window: bookings confirmed between 60 and 61 hours ago
    confirmed_before = now - timedelta(hours=REMINDER_AT_HOURS)
    confirmed_after = now - timedelta(hours=REMINDER_AT_HOURS + 1)

    # Subquery: booking IDs that already have a review
    reviewed_subq = select(Review.booking_id).scalar_subquery()

    result = await db.execute(
        select(Booking).where(
            and_(
                Booking.status == "CONFIRMED",
                Booking.confirmed_at.isnot(None),
                Booking.confirmed_at >= confirmed_after,
                Booking.confirmed_at <= confirmed_before,
                Booking.customer_email.isnot(None),
                Booking.id.notin_(reviewed_subq),
            )
        )
    )
    bookings = result.scalars().all()

    sent_count = 0
    failed_count = 0

    for booking in bookings:
        # Double-check: has a review reminder already been sent via the Review table?
        # (In case a Review row was created with reminder_sent=True by another path)
        existing = await db.execute(
            select(Review).where(Review.booking_id == booking.id)
        )
        if existing.scalar_one_or_none():
            continue

        # Get service and business names for the email
        svc_result = await db.execute(select(Service).where(Service.id == booking.service_id))
        service = svc_result.scalar_one_or_none()

        biz_result = await db.execute(select(Business).where(Business.id == booking.business_id))
        business = biz_result.scalar_one_or_none()

        service_name = service.service_name if service else "your booked service"
        business_name = business.business_name if business else "our business"

        deadline = booking.confirmed_at + timedelta(hours=REVIEW_WINDOW_HOURS)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        hours_left = max(0, round((deadline - now).total_seconds() / 3600, 1))

        success = await _send_reminder_email(
            to_email=booking.customer_email,
            customer_name=booking.customer_name or "Customer",
            tracking_id=booking.public_tracking_id,
            service_name=service_name,
            business_name=business_name,
            hours_left=hours_left,
        )

        if success:
            sent_count += 1
            logger.info(f"Review reminder sent for booking {booking.public_tracking_id}")
        else:
            failed_count += 1
            logger.warning(f"Failed to send review reminder for booking {booking.public_tracking_id}")

    return {
        "checked": len(bookings),
        "reminders_sent": sent_count,
        "failed": failed_count,
    }


async def _send_reminder_email(
    to_email: str,
    customer_name: str,
    tracking_id: str,
    service_name: str,
    business_name: str,
    hours_left: float,
) -> bool:
    """Send the review reminder email."""
    subject = f"Leave a Review — {tracking_id}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
            <tr>
                <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 26px;">&#11088; How was your experience?</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 30px;">
                    <h2 style="color: #333; margin-top: 0;">Hello {customer_name},</h2>
                    <p style="color: #666; font-size: 16px; line-height: 1.6;">
                        You recently used <strong>{service_name}</strong> at <strong>{business_name}</strong>.
                        We'd love to hear about your experience!
                    </p>
                    <p style="color: #666; font-size: 16px; line-height: 1.6;">
                        Your review window closes in approximately <strong>{hours_left} hours</strong>.
                        After that, you will no longer be able to leave a review.
                    </p>

                    <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 25px 0; text-align: center;">
                        <p style="margin: 0 0 10px; color: #666; font-size: 14px;">Your Booking ID</p>
                        <p style="margin: 0; font-size: 22px; font-weight: bold; color: #667eea;">{tracking_id}</p>
                    </div>

                    <p style="color: #999; font-size: 14px; line-height: 1.5;">
                        Use your booking ID or check your bookings list to leave a review.
                        Your feedback helps other customers and helps the business improve.
                    </p>
                </td>
            </tr>
            <tr>
                <td style="padding: 20px 30px; text-align: center; border-top: 1px solid #eee;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated reminder. You have {hours_left} hours remaining to submit your review.
                    </p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    text_content = f"""
HOW WAS YOUR EXPERIENCE?

Hello {customer_name},

You recently used {service_name} at {business_name}.
We'd love to hear about your experience!

Your review window closes in approximately {hours_left} hours.

Booking ID: {tracking_id}

Use your booking ID to find your booking and leave a review.
    """.strip()

    return await send_email(
        to_email=to_email,
        subject=subject,
        body=html_content,
        text=text_content,
    )
