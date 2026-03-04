from pydantic import BaseModel, Field
from datetime import datetime


class ReviewCreate(BaseModel):
    """Request body when a customer submits a review."""
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    description: str | None = Field(None, max_length=2000, description="Optional review text")


class ReviewResponse(BaseModel):
    """Review data returned to the client."""
    id: str
    booking_id: str
    service_id: str
    service_name: str | None = None
    customer_name: str | None = None
    rating: int
    description: str | None = None
    created_at: str


class ReviewEligibility(BaseModel):
    """Tells the frontend whether the user can leave a review for this booking."""
    can_review: bool
    reason: str | None = None  # e.g. "already_reviewed", "expired", "not_confirmed"
    expires_at: str | None = None  # ISO datetime when the 72h window closes
    hours_remaining: float | None = None


class BusinessReviewSummary(BaseModel):
    """Aggregated review stats for a business or service."""
    total_reviews: int
    average_rating: float | None = None
    reviews: list[ReviewResponse]
