# app/api/v1/bookings/router.py
from app.services.booking_status_history_service import set_booking_status

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional, Literal
import uuid
import secrets

from app.core.database import get_db
from app.models.service import Service
from app.models.booking import Booking

router = APIRouter(prefix="/bookings", tags=["Bookings"])


# ---------- Schemas ----------

class ReserveBookingRequest(BaseModel):
    business_id: str
    service_slug: str

    slot_start: datetime
    slot_end: datetime

    customer_name: str
    customer_phone: str
    customer_email: Optional[EmailStr] = None
    notes: Optional[str] = None

    # PAY_NOW / PAY_LATER (we won't generate stripe link yet in step 1)
    payment_choice: Literal["PAY_NOW", "PAY_LATER"] = "PAY_LATER"
class PayLaterResponse(BaseModel):
    public_tracking_id: str
    status: str
    payment_status: str

class ReserveBookingResponse(BaseModel):
    booking_id: str
    tracking_id: str
    status: str
    payment_status: str
    payment_choice: str


# ---------- Helpers ----------

def make_tracking_id() -> str:
    # Example: BK-A1B2C3 (6 chars)
    return "BK-" + secrets.token_hex(3).upper()


# ---------- Endpoint ----------

@router.post("/reserve", response_model=ReserveBookingResponse)
async def reserve_booking(
    payload: ReserveBookingRequest,
    db: AsyncSession = Depends(get_db),
):
    # validate business_id uuid
    try:
        business_uuid = uuid.UUID(payload.business_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid business_id")

    # basic slot validation
    if payload.slot_end <= payload.slot_start:
        raise HTTPException(status_code=400, detail="slot_end must be after slot_start")

    # find service by slug + business_id
    result = await db.execute(
        select(Service).where(
            Service.business_id == business_uuid,
            Service.slug == payload.service_slug,
            Service.is_active == True,
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found for this business")

    # create booking (NO payment session yet)
    booking = Booking(
        business_id=business_uuid,
        service_id=service.id,
        public_tracking_id=make_tracking_id(),

        # IMPORTANT: your DB has these columns
        status="INITIATED",          # exists in your enum (seen in table default)
        payment_status="CREATED",    # exists in your enum default

        slot_start=payload.slot_start,
        slot_end=payload.slot_end,

        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        customer_email=str(payload.customer_email) if payload.customer_email else None,
        notes=payload.notes,
    )

    db.add(booking)
    await db.commit()
    await db.refresh(booking)

    return ReserveBookingResponse(
        booking_id=str(booking.id),
        tracking_id=booking.public_tracking_id,
        status=str(booking.status),
        payment_status=str(booking.payment_status),
        payment_choice=payload.payment_choice,
    )
@router.patch("/{tracking_id}/pay-later", response_model=PayLaterResponse)
async def mark_booking_pay_later(
    tracking_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Booking).where(Booking.public_tracking_id == tracking_id)
    )
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # set pending
    await set_booking_status(db, booking, "PENDING_PAYMENT", reason="bookings_router", note="Pay later selected")

    booking.payment_status = "CREATED"
    booking.updated_at = datetime.utcnow()

   

    await db.commit()
    await db.refresh(booking)

    return PayLaterResponse(
        public_tracking_id=booking.public_tracking_id,
        status=booking.status,
        payment_status=booking.payment_status,
    )