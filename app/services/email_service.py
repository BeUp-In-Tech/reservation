import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.email import send_email
from app.core.config import settings
from app.models import Booking, Service, Business


class EmailService:
    """Service for sending emails."""
    
    @staticmethod
    async def send_booking_confirmation(booking: Booking, db: AsyncSession) -> bool:
        """
        Send booking confirmation email to customer.
        Called after successful payment.
        """
        if not booking.customer_email:
            print(f"No email for booking {booking.public_tracking_id}")
            return False
        
        # Get service details
        result = await db.execute(
            select(Service).where(Service.id == booking.service_id)
        )
        service = result.scalar_one_or_none()
        
        # Get business details
        result = await db.execute(
            select(Business).where(Business.id == booking.business_id)
        )
        business = result.scalar_one_or_none()
        
        # Format slot time
        slot_display = "Not scheduled"
        if booking.slot_start:
            slot_display = booking.slot_start.strftime("%B %d, %Y at %I:%M %p")
        
        # Create email content
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
                    <h1>Booking Confirmed! ✓</h1>
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
                                <td>Date & Time:</td>
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
        """
        
        # Send email
        return await EmailService._send_email(
            to_email=booking.customer_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    @staticmethod
    async def send_booking_pending(booking: Booking, db: AsyncSession, payment_url: str) -> bool:
        """
        Send booking pending email with payment link.
        Called when user chooses "Pay Later".
        """
        if not booking.customer_email:
            return False
        
        # Get service and business details
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
                        <p><strong>Date & Time:</strong> {slot_display}</p>
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
        """
        
        return await EmailService._send_email(
            to_email=booking.customer_email,
            subject=subject,
            html_content=html_content,
            text_content=text_content
        )
    
    @staticmethod
    async def _send_email(
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """
        Send email using SMTP.
        Configure SMTP settings in .env file.
        """
        try:
            # Check if SMTP is configured
            smtp_host = getattr(settings, 'SMTP_HOST', None)
            smtp_port = getattr(settings, 'SMTP_PORT', 587)
            smtp_user = getattr(settings, 'SMTP_USER', None)
            smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
            from_email = getattr(settings, 'FROM_EMAIL', 'noreply@example.com')
            
            if not smtp_host or not smtp_user:
                # SMTP not configured - just log
                print(f"[EMAIL] Would send to {to_email}: {subject}")
                print(f"[EMAIL] Content preview: {text_content[:200]}...")
                return True  # Return True to not block the flow
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = to_email
            
            # Attach parts
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(from_email, to_email, msg.as_string())
            
            print(f"[EMAIL] Sent to {to_email}: {subject}")
            return True
            
        except Exception as e:
            print(f"[EMAIL ERROR] Failed to send to {to_email}: {str(e)}")
            return False

    
    @staticmethod

    async def send_contact_form_to_admin(
        name: str,
        email: str,
        subject: str,
        message: str
    ) -> bool:
        """
        Send contact form submission to admin email using Resend.
        """
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
                    <h1>📧 New Contact Form Submission</h1>
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
            reply_to=email,   # ✅ so admin can hit Reply and it goes to user
            text=text_content
        )