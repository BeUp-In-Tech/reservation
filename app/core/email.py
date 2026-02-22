import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
async def send_email(
    to_email: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
    text: str | None = None,
) -> bool:
    """Send email using Gmail SMTP."""
    try:
        smtp_host = settings.SMTP_HOST
        smtp_port = settings.SMTP_PORT
        smtp_user = settings.SMTP_USER
        smtp_password = settings.SMTP_PASSWORD
        from_email = settings.FROM_EMAIL

        if not smtp_host or not smtp_user or not smtp_password:
            print("[EMAIL ERROR] SMTP not configured")
            return False

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        if reply_to:
            msg["Reply-To"] = reply_to

        # Attach text and HTML
        if text:
            msg.attach(MIMEText(text, "plain")) 
        msg.attach(MIMEText(body, "html"))

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())

        print(f"[EMAIL] Sent to {to_email}: {subject}")
        return True

    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
        return False
async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email with branded template."""

    reset_link = f"https://reservation-xynh.onrender.com/api/v1/admin/auth/reset-password?token={reset_token}"

    subject = "🔐 Password Reset Request - Reservation System"
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
            <!-- Header -->
            <tr>
                <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 28px;">🔐 Password Reset</h1>
                </td>
            </tr>
            
            <!-- Body -->
            <tr>
                <td style="padding: 40px 30px;">
                    <h2 style="color: #333; margin-top: 0;">Hello,</h2>
                    <p style="color: #666; font-size: 16px; line-height: 1.6;">
                        We received a request to reset your password for your Reservation System admin account.
                    </p>
                    <p style="color: #666; font-size: 16px; line-height: 1.6;">
                        Click the button below to set a new password:
                    </p>
                    
                    <!-- CTA Button -->
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0;">
                        <tr>
                            <td align="center">
                                <a href="{reset_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 15px 40px; text-decoration: none; border-radius: 50px; font-size: 16px; font-weight: bold; display: inline-block;">
                                    Reset My Password
                                </a>
                            </td>
                        </tr>
                    </table>
                    
                    <p style="color: #999; font-size: 14px; line-height: 1.6;">
                        Or copy and paste this link in your browser:
                    </p>
                    <p style="background: #f8f9fa; padding: 15px; border-radius: 8px; word-break: break-all; font-family: monospace; font-size: 12px; color: #666;">
                        {reset_link}
                    </p>
                    
                    <!-- Warning -->
                    <table width="100%" style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
                        <tr>
                            <td>
                                <p style="margin: 0; color: #856404; font-size: 14px;">
                                    ⚠️ This link expires in <strong>1 hour</strong>. If you didn't request this, please ignore this email.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            
            <!-- Footer -->
            <tr>
                <td style="background: #f8f9fa; padding: 20px 30px; text-align: center; border-top: 1px solid #eee;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        © 2024 Reservation System. All rights reserved.
                    </p>
                    <p style="color: #999; font-size: 12px; margin: 10px 0 0 0;">
                        This is an automated message. Please do not reply.
                    </p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return await send_email(to_email, subject, body)


async def send_booking_confirmation_email(to_email: str, booking_data: dict) -> bool:
    """Send booking confirmation email."""

    subject = "✅ Booking Confirmed - Reservation System"
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
            <tr>
                <td style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0;">✅ Booking Confirmed!</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 30px;">
                    <h2 style="color: #333;">Hello {booking_data.get('customer_name', 'Customer')},</h2>
                    <p style="color: #666; font-size: 16px;">Your booking has been confirmed! Here are the details:</p>
                    
                    <table style="width: 100%; background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <tr>
                            <td style="padding: 10px; color: #666;"><strong>Booking ID:</strong></td>
                            <td style="padding: 10px; color: #333;">{booking_data.get('tracking_id', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; color: #666;"><strong>Service:</strong></td>
                            <td style="padding: 10px; color: #333;">{booking_data.get('service_name', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; color: #666;"><strong>Date & Time:</strong></td>
                            <td style="padding: 10px; color: #333;">{booking_data.get('slot_start', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; color: #666;"><strong>Status:</strong></td>
                            <td style="padding: 10px; color: #28a745; font-weight: bold;">{booking_data.get('status', 'CONFIRMED')}</td>
                        </tr>
                    </table>
                    
                    <p style="color: #666; font-size: 14px;">Thank you for your booking!</p>
                </td>
            </tr>
            <tr>
                <td style="background: #f8f9fa; padding: 20px; text-align: center;">
                    <p style="color: #999; font-size: 12px; margin: 0;">© 2024 Reservation System</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return await send_email(to_email, subject, body)


async def send_booking_cancellation_email(to_email: str, booking_data: dict) -> bool:
    """Send booking cancellation email."""

    subject = "❌ Booking Cancelled - Reservation System"
    body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
    </head>
    <body style="margin:0; padding:0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">
            <tr>
                <td style="background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0;">❌ Booking Cancelled</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 30px;">
                    <h2 style="color: #333;">Hello {booking_data.get('customer_name', 'Customer')},</h2>
                    <p style="color: #666; font-size: 16px;">Your booking has been cancelled.</p>
                    
                    <table style="width: 100%; background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <tr>
                            <td style="padding: 10px; color: #666;"><strong>Booking ID:</strong></td>
                            <td style="padding: 10px; color: #333;">{booking_data.get('tracking_id', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; color: #666;"><strong>Service:</strong></td>
                            <td style="padding: 10px; color: #333;">{booking_data.get('service_name', 'N/A')}</td>
                        </tr>
                    </table>
                    
                    <p style="color: #666; font-size: 14px;">If you have any questions, please contact us.</p>
                </td>
            </tr>
            <tr>
                <td style="background: #f8f9fa; padding: 20px; text-align: center;">
                    <p style="color: #999; font-size: 12px; margin: 0;">© 2024 Reservation System</p>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return await send_email(to_email, subject, body)
