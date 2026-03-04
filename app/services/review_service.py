"""
Review business logic.
Handles eligibility checks, creation, and queries.
"""

import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.booking import Booking
from app.models.service import Service
from app.models.review import Review

logger = logging.getLogger(__name__)

# Review window: 72 hours after booking confirmation
REVIEW_WINDOW_HOURS = 72
# Reminder sent 12 hours before expiry (i.e. at the 60-hour mark)
REMINDER_OFFSET_HOURS = REVIEW_WINDOW_HOURS - 12  # 60


def _get_review_deadline(confirmed_at: datetime) -> datetime:
    """Return the UTC datetime when the review window closes."""
    if confirmed_at.tzinfo is None:
        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
    return confirmed_at + timedelta(hours=REVIEW_WINDOW_HOURS)


async def check_review_eligibility(
    db: AsyncSession,
    booking: Booking,
) -> dict:
    """
    Check if a booking is eligible for a review.
    Returns dict with can_review, reason, expires_at, hours_remaining.
    """
    # Must be CONFIRMED
    if booking.status != "CONFIRMED":
        return {
            "can_review": False,
            "reason": "not_confirmed",
            "expires_at": None,
            "hours_remaining": None,
        }

    # Must have confirmed_at timestamp
    if not booking.confirmed_at:
        return {
            "can_review": False,
            "reason": "not_confirmed",
            "expires_at": None,
            "hours_remaining": None,
        }

    # Check if already reviewed
    result = await db.execute(
        select(Review).where(Review.booking_id == booking.id)
    )
    existing_review = result.scalar_one_or_none()

    if existing_review:
        return {
            "can_review": False,
            "reason": "already_reviewed",
            "expires_at": None,
            "hours_remaining": None,
        }

    # Check 72-hour window
    deadline = _get_review_deadline(booking.confirmed_at)
    now = datetime.now(timezone.utc)

    if now > deadline:
        return {
            "can_review": False,
            "reason": "expired",
            "expires_at": deadline.isoformat(),
            "hours_remaining": 0,
        }

    hours_remaining = (deadline - now).total_seconds() / 3600

    return {
        "can_review": True,
        "reason": None,
        "expires_at": deadline.isoformat(),
        "hours_remaining": round(hours_remaining, 2),
    }


async def create_review(
    db: AsyncSession,
    booking: Booking,
    rating: int,
    description: str | None,
) -> Review:
    """
    Create a review for a confirmed booking.
    Caller must verify eligibility first.
    """
    review = Review(
        business_id=booking.business_id,
        service_id=booking.service_id,
        booking_id=booking.id,
        customer_name=booking.customer_name,
        customer_email=booking.customer_email,
        rating=rating,
        description=description,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    logger.info(f"Review created for booking {booking.public_tracking_id} — rating={rating}")
    return review


async def get_reviews_for_business(
    db: AsyncSession,
    business_id,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Review], int, float | None]:
    """
    Get reviews for a business.
    Returns (reviews, total_count, average_rating).
    """
    # Count + average
    stats = await db.execute(
        select(
            func.count(Review.id),
            func.avg(Review.rating),
        ).where(Review.business_id == business_id)
    )
    row = stats.one()
    total_count = row[0] or 0
    avg_rating = round(float(row[1]), 2) if row[1] else None

    # Fetch reviews
    result = await db.execute(
        select(Review)
        .where(Review.business_id == business_id)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    reviews = result.scalars().all()

    return reviews, total_count, avg_rating


async def get_reviews_for_service(
    db: AsyncSession,
    service_id,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Review], int, float | None]:
    """
    Get reviews for a specific service.
    Returns (reviews, total_count, average_rating).
    """
    stats = await db.execute(
        select(
            func.count(Review.id),
            func.avg(Review.rating),
        ).where(Review.service_id == service_id)
    )
    row = stats.one()
    total_count = row[0] or 0
    avg_rating = round(float(row[1]), 2) if row[1] else None

    result = await db.execute(
        select(Review)
        .where(Review.service_id == service_id)
        .order_by(Review.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    reviews = result.scalars().all()

    return reviews, total_count, avg_rating
