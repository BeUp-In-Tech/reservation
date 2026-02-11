from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.core.config import settings
from app.schemas.payment import (
    PaymentIntentCreate,
    PaymentIntentResponse,
    PaymentConfirmRequest,
    PaymentConfirmResponse,
    PayLaterRequest,
    PayLaterResponse,
)
from app.services.stripe_payment_service import StripePaymentService
from app.models import Booking

router = APIRouter()


@router.post("/payments/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(
    request: PaymentIntentCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create Stripe Checkout Session using booking_id (BK-XXXXXX)."""
    try:
        result = await StripePaymentService.create_payment_for_booking_id(
            booking_id=request.booking_id.strip(),
            db=db
        )
        return PaymentIntentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payments/pay-later", response_model=PayLaterResponse)
async def pay_later(
    request: PayLaterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Get payment link for pending booking using booking_id (BK-XXXXXX)."""
    try:
        result = await StripePaymentService.create_payment_for_booking_id(
            booking_id=request.booking_id.strip(),
            db=db
        )
        return PayLaterResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payments/confirm", response_model=PaymentConfirmResponse)
async def confirm_payment(
    request: PaymentConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    """Confirm payment after Stripe processing."""
    try:
        result = await StripePaymentService.confirm_payment(
            session_id=request.session_id,
            db=db
        )
        return PaymentConfirmResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/webhooks/stripe")
async def stripe_webhook(
    
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    print("✅ STRIPE WEBHOOK HIT")
    """Handle Stripe webhook events."""
    import stripe
    import json

    payload = await request.body()
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    if webhook_secret and stripe_signature:
        try:
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=stripe_signature,
                secret=webhook_secret,
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        event = json.loads(payload.decode("utf-8"))

    business_id = None
    obj = event.get("data", {}).get("object", {}) if isinstance(event, dict) else {}
    bid = (obj.get("metadata") or {}).get("business_id")
    if bid:
        try:
            business_id = UUID(bid)
        except:
            pass

    return await StripePaymentService.handle_webhook(
        event_type=event["type"],
        event_data=event.get("data", {}),
        db=db,
        business_id=business_id,
        provider_event_id=event.get("id"),
    )
