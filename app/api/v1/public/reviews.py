"""
Public review endpoints.
Customers can submit reviews and view reviews for businesses/services.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.core.database import get_db
from app.models.booking import Booking
from app.models.service import Service
from app.models.business import Business
from app.models.review import Review
from app.schemas.review import (
    ReviewCreate,
    ReviewResponse,
    ReviewEligibility,
    BusinessReviewSummary,
)
from app.services.review_service import (
    check_review_eligibility,
    create_review,
    get_reviews_for_business,
    get_reviews_for_service,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


# ---------- Submit a review ----------

@router.post("/bookings/{tracking_id}", response_model=ReviewResponse)
async def submit_review(
    tracking_id: str,
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a review for a confirmed booking.
    The booking must be CONFIRMED and within the 72-hour review window.
    Only one review per booking is allowed.
    """
    # Find booking
    result = await db.execute(
        select(Booking).where(Booking.public_tracking_id == tracking_id.upper())
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check eligibility
    eligibility = await check_review_eligibility(db, booking)

    if not eligibility["can_review"]:
        reason = eligibility["reason"]
        messages = {
            "not_confirmed": "Only confirmed bookings can be reviewed.",
            "already_reviewed": "You have already submitted a review for this booking.",
            "expired": "The 72-hour review window has expired for this booking.",
        }
        raise HTTPException(
            status_code=400,
            detail=messages.get(reason, "You cannot review this booking."),
        )

    # Create review
    review = await create_review(
        db=db,
        booking=booking,
        rating=payload.rating,
        description=payload.description,
    )

    # Get service name
    svc_result = await db.execute(select(Service).where(Service.id == review.service_id))
    service = svc_result.scalar_one_or_none()

    return ReviewResponse(
        id=str(review.id),
        booking_id=str(review.booking_id),
        service_id=str(review.service_id),
        service_name=service.service_name if service else None,
        customer_name=review.customer_name,
        rating=review.rating,
        description=review.description,
        created_at=review.created_at.isoformat(),
    )


# ---------- Check review eligibility ----------

@router.get("/bookings/{tracking_id}/eligibility", response_model=ReviewEligibility)
async def check_booking_review_eligibility(
    tracking_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Check if a booking is eligible for a review.
    The frontend uses this to show/hide the review button.
    """
    result = await db.execute(
        select(Booking).where(Booking.public_tracking_id == tracking_id.upper())
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    eligibility = await check_review_eligibility(db, booking)

    return ReviewEligibility(**eligibility)


# ---------- Get reviews for a business ----------

@router.get("/business/{business_slug}", response_model=BusinessReviewSummary)
async def get_business_reviews(
    business_slug: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get all reviews for a business (public)."""
    result = await db.execute(
        select(Business).where(Business.slug == business_slug, Business.is_active == True)
    )
    business = result.scalar_one_or_none()

    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    reviews, total_count, avg_rating = await get_reviews_for_business(
        db, business.id, limit, offset
    )

    # Get service names for all reviews
    service_ids = list({r.service_id for r in reviews})
    services_dict = {}
    if service_ids:
        svc_result = await db.execute(select(Service).where(Service.id.in_(service_ids)))
        services_dict = {s.id: s.service_name for s in svc_result.scalars().all()}

    return BusinessReviewSummary(
        total_reviews=total_count,
        average_rating=avg_rating,
        reviews=[
            ReviewResponse(
                id=str(r.id),
                booking_id=str(r.booking_id),
                service_id=str(r.service_id),
                service_name=services_dict.get(r.service_id),
                customer_name=r.customer_name,
                rating=r.rating,
                description=r.description,
                created_at=r.created_at.isoformat(),
            )
            for r in reviews
        ],
    )


# ---------- Get reviews for a service ----------

@router.get("/service/{service_id}", response_model=BusinessReviewSummary)
async def get_service_reviews(
    service_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get all reviews for a specific service (public)."""
    try:
        svc_uuid = uuid.UUID(service_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid service_id")

    result = await db.execute(select(Service).where(Service.id == svc_uuid))
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    reviews, total_count, avg_rating = await get_reviews_for_service(
        db, svc_uuid, limit, offset
    )

    return BusinessReviewSummary(
        total_reviews=total_count,
        average_rating=avg_rating,
        reviews=[
            ReviewResponse(
                id=str(r.id),
                booking_id=str(r.booking_id),
                service_id=str(r.service_id),
                service_name=service.service_name,
                customer_name=r.customer_name,
                rating=r.rating,
                description=r.description,
                created_at=r.created_at.isoformat(),
            )
            for r in reviews
        ],
    )
