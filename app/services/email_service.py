from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.email import send_email
from app.core.config import settings
from app.models import Booking, Service, Business


class EmailService:
    """Service for sending emails via SendGrid."""

    @staticmethod
    async def send_booking_confirmation(booking: Booking, db: AsyncSession) -> bool:
        """Send booking confirmation email to customer after successful payment."""
        if not booking.customer_email:
            print(f"No email for booking {booking.public_tracking_id}")
            return False

        result = await db.execute(select(Service).where(Service.id == booking.service_id))
        service = result.scalar_one_or_none()

        result = await db.execute(select(Business).where(Business.id == booking.business_id))
        business = result.scalar_one_or_none()

        slot_display = "Not scheduled"
        if booking.slot_start:
            slot_display = booking.slot_start.strftime("%B %d, %Y at %I:%M %p")

        subject = f"Booking Confirmed - {booking.public_tracking_id}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .details table {{ width: 100%; }}
                .details td {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
                .details td:first-child {{ font-weight: bold; width: 40%; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .tracking-id {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Booking Confirmed! &#10003;</h1>
                </div>
                <div class="content">
                    <p>Dear {booking.customer_name or 'Customer'},</p>
                    <p>Your booking has been confirmed. Here are your details:</p>

                    <div class="details">
                        <p class="tracking-id">{booking.public_tracking_id}</p>
                        <table>
                            <tr>
                                <td>Service:</td>
                                <td>{service.service_name if service else 'N/A'}</td>
                            </tr>
                            <tr>
                                <td>Date &amp; Time:</td>
                                <td>{slot_display}</td>
                            </tr>
                            <tr>
                                <td>Business:</td>
                                <td>{business.business_name if business else 'N/A'}</td>
                            </tr>
                            <tr>
                                <td>Amount Paid:</td>
                                <td>{booking.payment_amount or 0} {booking.payment_currency or 'USD'}</td>
                            </tr>
                            <tr>
                                <td>Status:</td>
                                <td><strong style="color: #4CAF50;">CONFIRMED</strong></td>
                            </tr>
                        </table>
                    </div>

                    <p>Please save your Booking ID: <strong>{booking.public_tracking_id}</strong></p>
                    <p>You can use this ID to check your booking status or make changes.</p>

                    <p>Thank you for choosing us!</p>
                </div>
                <div class="footer">
                    <p>This is an automated email. Please do not reply.</p>
                    <p>&copy; {datetime.now().year} {business.business_name if business else 'AI Booking System'}</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
BOOKING CONFIRMED

Dear {booking.customer_name or 'Customer'},

Your booking has been confirmed!

Booking ID: {booking.public_tracking_id}
Service: {service.service_name if service else 'N/A'}
Date & Time: {slot_display}
Business: {business.business_name if business else 'N/A'}
Amount Paid: {booking.payment_amount or 0} {booking.payment_currency or 'USD'}
Status: CONFIRMED

Thank you for choosing us!
        """.strip()

        return await send_email(
            to_email=booking.customer_email,
            subject=subject,
            body=html_content,
            text=text_content,
        )

    @staticmethod
    async def send_booking_pending(booking: Booking, db: AsyncSession, payment_url: str) -> bool:
        """Send booking pending email with payment link."""
        if not booking.customer_email:
            return False

        result = await db.execute(select(Service).where(Service.id == booking.service_id))
        service = result.scalar_one_or_none()

        result = await db.execute(select(Business).where(Business.id == booking.business_id))
        business = result.scalar_one_or_none()

        slot_display = booking.slot_start.strftime("%B %d, %Y at %I:%M %p") if booking.slot_start else "Not scheduled"

        subject = f"Complete Your Booking - {booking.public_tracking_id}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #FF9800; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .details {{ background-color: white; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .pay-button {{ display: inline-block; background-color: #4CAF50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Complete Your Booking</h1>
                </div>
                <div class="content">
                    <p>Dear {booking.customer_name or 'Customer'},</p>
                    <p>Your booking is reserved but <strong>payment is pending</strong>.</p>

                    <div class="details">
                        <p><strong>Booking ID:</strong> {booking.public_tracking_id}</p>
                        <p><strong>Service:</strong> {service.service_name if service else 'N/A'}</p>
                        <p><strong>Date &amp; Time:</strong> {slot_display}</p>
                        <p><strong>Amount Due:</strong> {service.base_price if service else 0} {service.currency if service else 'USD'}</p>
                    </div>

                    <p style="text-align: center; margin: 30px 0;">
                        <a href="{payment_url}" class="pay-button">Complete Payment Now</a>
                    </p>

                    <p><small>Or use your Booking ID <strong>{booking.public_tracking_id}</strong> to pay later.</small></p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.now().year} {business.business_name if business else 'AI Booking System'}</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
COMPLETE YOUR BOOKING

Dear {booking.customer_name or 'Customer'},

Your booking is reserved but payment is pending.

Booking ID: {booking.public_tracking_id}
Service: {service.service_name if service else 'N/A'}
Date & Time: {slot_display}
Amount Due: {service.base_price if service else 0} {service.currency if service else 'USD'}

Complete your payment here: {payment_url}

Or use your Booking ID to pay later.
        """.strip()

        return await send_email(
            to_email=booking.customer_email,
            subject=subject,
            body=html_content,
            text=text_content,
        )

    @staticmethod
    async def send_payment_notification(booking: Booking, db: AsyncSession) -> bool:
        """Send payment notification email to business owner and admin after successful Stripe payment."""
        from app.models.other_models import AdminUser

        result = await db.execute(select(Service).where(Service.id == booking.service_id))
        service = result.scalar_one_or_none()

        result = await db.execute(select(Business).where(Business.id == booking.business_id))
        business = result.scalar_one_or_none()

        # Get business owner email
        owner_email = None
        if business and business.created_by_admin_id:
            result = await db.execute(
                select(AdminUser).where(AdminUser.id == business.created_by_admin_id)
            )
            owner = result.scalar_one_or_none()
            if owner:
                owner_email = owner.email

        # Admin email from settings
        admin_email = getattr(settings, "ADMIN_EMAIL", None)

        # Deduplicated recipients
        recipients = set()
        if owner_email:
            recipients.add(owner_email)
        if admin_email:
            recipients.add(admin_email)

        if not recipients:
            print("[EMAIL] No recipients for payment notification")
            return False

        service_name = service.service_name if service else "N/A"
        business_name = business.business_name if business else "N/A"
        amount = booking.payment_amount or (service.base_price if service else 0) or 0
        currency = booking.payment_currency or (service.currency if service else "USD") or "USD"
        slot_display = booking.slot_start.strftime("%B %d, %Y at %I:%M %p") if booking.slot_start else "Not scheduled"
        customer_name = booking.customer_name or "N/A"
        customer_email_addr = booking.customer_email or "N/A"
        customer_phone = booking.customer_phone or "N/A"

        subject = f"Payment Received - {booking.public_tracking_id} - {service_name}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .amount-box {{ background-color: #ffffff; padding: 20px; border-radius: 8px; text-align: center; margin: 15px 0; border: 2px solid #38ef7d; }}
                .amount {{ font-size: 32px; font-weight: bold; color: #11998e; }}
                .details {{ background-color: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
                .details table {{ width: 100%; border-collapse: collapse; }}
                .details td {{ padding: 10px 8px; border-bottom: 1px solid #eee; }}
                .details td:first-child {{ font-weight: bold; width: 40%; color: #666; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">&#128176; Payment Received!</h1>
                    <p style="margin: 5px 0 0; opacity: 0.9;">A customer has completed payment</p>
                </div>
                <div class="content">
                    <div class="amount-box">
                        <p style="margin: 0; color: #666; font-size: 14px;">Amount Paid</p>
                        <p class="amount">{amount} {currency}</p>
                    </div>

                    <div class="details">
                        <h3 style="margin-top: 0; color: #333;">Booking Details</h3>
                        <table>
                            <tr>
                                <td>Booking ID:</td>
                                <td><strong>{booking.public_tracking_id}</strong></td>
                            </tr>
                            <tr>
                                <td>Service:</td>
                                <td>{service_name}</td>
                            </tr>
                            <tr>
                                <td>Business:</td>
                                <td>{business_name}</td>
                            </tr>
                            <tr>
                                <td>Date &amp; Time:</td>
                                <td>{slot_display}</td>
                            </tr>
                        </table>
                    </div>

                    <div class="details">
                        <h3 style="margin-top: 0; color: #333;">Customer Info</h3>
                        <table>
                            <tr>
                                <td>Name:</td>
                                <td>{customer_name}</td>
                            </tr>
                            <tr>
                                <td>Email:</td>
                                <td>{customer_email_addr}</td>
                            </tr>
                            <tr>
                                <td>Phone:</td>
                                <td>{customer_phone}</td>
                            </tr>
                        </table>
                    </div>

                    <p style="color: #666; font-size: 13px;">Status: <strong style="color: #11998e;">CONFIRMED &amp; PAID</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated notification from {business_name}.</p>
                    <p>&copy; {datetime.now().year} {business_name}</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
PAYMENT RECEIVED

Amount Paid: {amount} {currency}

Booking ID: {booking.public_tracking_id}
Service: {service_name}
Business: {business_name}
Date & Time: {slot_display}

Customer: {customer_name}
Email: {customer_email_addr}
Phone: {customer_phone}

Status: CONFIRMED & PAID
        """.strip()

        success = True
        for recipient in recipients:
            sent = await send_email(
                to_email=recipient,
                subject=subject,
                body=html_content,
                text=text_content,
            )
            if not sent:
                success = False

        return success

    @staticmethod
    async def send_contact_form_to_admin(
        name: str,
        email: str,
        subject: str,
        message: str
    ) -> bool:
        """Send contact form submission to admin email."""
        admin_email = getattr(settings, "ADMIN_EMAIL", "admin@example.com")
        email_subject = f"[Contact Form] {subject}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2196F3; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .message-box {{ background-color: #fff; padding: 20px; border-left: 4px solid #2196F3; margin: 20px 0; }}
                .reply-button {{ display: inline-block; background-color: #4CAF50; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>New Contact Form Submission</h1>
                </div>
                <div class="content">
                    <p>From: <strong>{name}</strong> ({email})</p>
                    <p>Subject: {subject}</p>
                    <div class="message-box">
                        <p style="white-space: pre-wrap;">{message}</p>
                    </div>
                    <p style="text-align: center;">
                        <a href="mailto:{email}?subject=Re: {subject}" class="reply-button">Reply to {name}</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        text_content = f"""
NEW CONTACT FORM SUBMISSION

From: {name}
Email: {email}
Subject: {subject}

Message:
{message}
        """.strip()

        return await send_email(
            to_email=admin_email,
            subject=email_subject,
            body=html_content,
            reply_to=email,
            text=text_content,
        )