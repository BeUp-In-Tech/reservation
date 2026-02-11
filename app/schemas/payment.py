from pydantic import BaseModel, Field
from uuid import UUID


class PaymentIntentCreate(BaseModel):
    """Create payment using booking_id (BK-XXXXXX)"""
    booking_id: str = Field(..., description="Booking ID like BK-040613")


class PaymentIntentResponse(BaseModel):
    payment_session_id: str
    client_secret: str
    amount: float
    currency: str
    status: str
    publishable_key: str
    payment_url: str
    booking_id: str = Field(..., description="Booking ID like BK-040613")


class PaymentConfirmRequest(BaseModel):
    session_id: str = Field(..., description="Stripe session ID (cs_test_...)")


class PaymentConfirmResponse(BaseModel):
    success: bool
    payment_status: str
    booking_id: str
    message: str


class PayLaterRequest(BaseModel):
    booking_id: str = Field(..., description="Booking ID like BK-040613")


class PayLaterResponse(BaseModel):
    success: bool
    booking_id: str
    payment_url: str
    client_secret: str
    amount: float
    currency: str
    message: str
