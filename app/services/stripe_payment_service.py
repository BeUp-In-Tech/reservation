import stripe

from datetime import datetime
from uuid import UUID
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.services.booking_status_history_service import set_booking_status

from app.core.config import settings
from app.models import Booking, Business, Service
from app.models.other_models import PaymentSession, PaymentEvent
from app.services.email_service import EmailService

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripePaymentService:

    @staticmethod
    def _service_display_name(service) -> str:
        for attr in ("name", "service_name", "title", "display_name"):
            val = getattr(service, attr, None)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return "Service"

    @staticmethod
    async def create_payment_for_booking_id(booking_id: str, db: AsyncSession) -> dict:
        """Create Stripe Checkout Session using booking_id (BK-XXXXXX)."""
        booking_id = booking_id.strip()

        # Find booking by public_tracking_id (BK-XXXXXX)
        result = await db.execute(
            select(Booking).where(Booking.public_tracking_id == booking_id)
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {booking_id}")

        if booking.status == "CANCELLED":
            raise ValueError("Booking has been cancelled")

        if booking.status == "CONFIRMED" or booking.payment_status == "PAID":
            raise ValueError("Booking is already confirmed and paid")

        # Get service
        result = await db.execute(select(Service).where(Service.id == booking.service_id))
        service = result.scalar_one_or_none()
        if not service:
            raise ValueError("Service not found for booking")

        # Get business
        result = await db.execute(select(Business).where(Business.id == booking.business_id))
        business = result.scalar_one_or_none()

        amount = service.base_price or Decimal("0.00")
        currency = (getattr(service, "currency", "USD") or "USD").strip().upper()

        success_url = getattr(settings, "PAYMENT_SUCCESS_URL", "https://yourdomain.com/payment/success") + f"?booking_id={booking.public_tracking_id}"
        cancel_url = getattr(settings, "PAYMENT_CANCEL_URL", "https://yourdomain.com/payment/cancel") + f"?booking_id={booking.public_tracking_id}"

        # Check for existing PENDING session
        result = await db.execute(
            select(PaymentSession)
            .where(PaymentSession.booking_id == booking.id)
            .where(PaymentSession.status == "PENDING")
            .order_by(PaymentSession.created_at.desc())
        )
        pending_sessions = result.scalars().all()

        # Reuse existing session if still open
        if pending_sessions:
            newest = pending_sessions[0]
            if newest.provider_session_id and str(newest.provider_session_id).startswith("cs_"):
                try:
                    session = stripe.checkout.Session.retrieve(newest.provider_session_id)
                    if getattr(session, "status", None) == "open":
                        for old in pending_sessions[1:]:
                            old.status = "EXPIRED"
                        await db.commit()
                        return {
                            "payment_session_id": str(newest.id),
                            "client_secret": newest.provider_session_id,
                            "amount": float(newest.amount),
                            "currency": newest.currency.strip(),
                            "status": newest.status,
                            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
                            "payment_url": newest.payment_url,
                            "booking_id": booking.public_tracking_id,
                            "success": True,
                            "message": "Existing payment session retrieved",
                        }
                except stripe.error.StripeError:
                    pass

            # Expire old sessions
            for ps in pending_sessions:
                ps.status = "EXPIRED"
            await db.commit()

        # Create new Stripe Checkout Session
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {
                            "name": StripePaymentService._service_display_name(service)
                        },
                        "unit_amount": int(amount * 100),
                    },
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "booking_id": str(booking.id),
                    "business_id": str(booking.business_id),
                    "tracking_id": booking.public_tracking_id,
                },
            )
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe error: {str(e)}")

        # Save payment session
        payment_session = PaymentSession(
            business_id=booking.business_id,
            booking_id=booking.id,
            provider="stripe",
            provider_session_id=checkout_session.id,
            amount=amount,
            currency=currency,
            status="PENDING",
            payment_url=checkout_session.url,
        )
        db.add(payment_session)
        await db.commit()
        await db.refresh(payment_session)

        return {
            "payment_session_id": str(payment_session.id),
            "client_secret": checkout_session.id,
            "amount": float(amount),
            "currency": currency,
            "status": "PENDING",
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "payment_url": checkout_session.url,
            "booking_id": booking.public_tracking_id,
            "success": True,
            "message": "Payment session created",
        }

    @staticmethod
    async def confirm_payment(session_id: str, db: AsyncSession) -> dict:
        """Confirm payment from Stripe session ID."""
        result = await db.execute(
            select(PaymentSession).where(PaymentSession.provider_session_id == session_id)
        )
        payment_session = result.scalar_one_or_none()
        if not payment_session:
            raise ValueError("Payment session not found")

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            raise ValueError(f"Stripe error: {str(e)}")

        result = await db.execute(select(Booking).where(Booking.id == payment_session.booking_id))
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError("Booking not found")

        payment_status = (getattr(session, "payment_status", "") or "").lower()

        if payment_status == "paid":
            payment_session.status = "COMPLETED"
            payment_session.paid_at = datetime.utcnow()
            booking.payment_status = "PAID"
            booking.paid_at = datetime.utcnow()
            await set_booking_status(db, booking, "CONFIRMED", reason="stripe_confirm_payment", note=f"paid session={session_id}")

            booking.confirmed_at = datetime.utcnow()
            await db.commit()

            try:
                await EmailService.send_booking_confirmation(booking, db)
                await EmailService.send_payment_notification(booking, db)
            except:
                pass

            return {
                "success": True,
                "payment_status": "PAID",
                "booking_id": booking.public_tracking_id,
                "message": "Payment confirmed. Booking is now confirmed.",
            }

        return {
            "success": False,
            "payment_status": payment_status.upper() if payment_status else "UNKNOWN",
            "booking_id": booking.public_tracking_id,
            "message": f"Payment status: {payment_status or 'unknown'}",
        }

    @staticmethod
    async def handle_webhook(
        event_type: str,
        event_data: dict,
        db: AsyncSession,
        business_id: UUID | None = None,
        provider_event_id: str | None = None,
    ) -> dict:
        """Handle Stripe webhook events."""
        
        if provider_event_id:
            try:
                pe = PaymentEvent(
                    business_id=business_id,
                    provider="stripe",
                    provider_event_id=provider_event_id,
                    event_type=event_type,
                    payload=event_data,
                )
                db.add(pe)
                await db.commit()
            except IntegrityError:
                await db.rollback()

        obj = (event_data or {}).get("object", {}) if isinstance(event_data, dict) else {}
        session_id = obj.get("id")

        if not session_id:
            return {"success": True, "message": "No session id in webhook"}

        result = await db.execute(
            select(PaymentSession).where(PaymentSession.provider_session_id == session_id)
        )
        ps = result.scalar_one_or_none()
        if not ps:
            return {"success": False, "message": f"PaymentSession not found: {session_id}"}

        result = await db.execute(select(Booking).where(Booking.id == ps.booking_id))
        booking = result.scalar_one_or_none()

        if event_type == "checkout.session.completed":
            ps.status = "COMPLETED"
            ps.paid_at = datetime.utcnow()
            if booking:
                booking.payment_status = "PAID"
                booking.paid_at = datetime.utcnow()
                await set_booking_status(db, booking, "CONFIRMED", reason="stripe_webhook", note=f"checkout.session.completed session={session_id}")

                booking.confirmed_at = datetime.utcnow()
                try:
                    await EmailService.send_booking_confirmation(booking, db)
                    await EmailService.send_payment_notification(booking, db)
                except:
                    pass
            await db.commit()
            return {"success": True, "message": "Payment completed", "booking_id": booking.public_tracking_id if booking else None}

        if event_type == "checkout.session.expired":
            ps.status = "EXPIRED"
            await db.commit()
            return {"success": True, "message": "Payment expired"}

        return {"success": True, "message": f"Ignored: {event_type}"}
