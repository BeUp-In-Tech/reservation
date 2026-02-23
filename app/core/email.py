import httpx
from app.core.config import settings


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
    text: str | None = None,
) -> bool:
    """Send email using SendGrid API."""
    try:
        api_key = settings.SENDGRID_API_KEY
        from_email = settings.FROM_EMAIL

        if not api_key:
            print("[EMAIL ERROR] SENDGRID_API_KEY not configured")
            return False

        url = "https://api.sendgrid.com/v3/mail/send"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Build content array
        content = [{"type": "text/html", "value": body}]
        if text:
            content.insert(0, {"type": "text/plain", "value": text})

        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": content
        }

        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code in [200, 202]:
            print(f"[EMAIL] Sent to {to_email}: {subject}")
            return True
        else:
            print(f"[EMAIL ERROR] SendGrid returned {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {to_email}: {e}")
        return False


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email."""
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
            <tr>
                <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 28px;">🔐 Password Reset</h1>
                </td>
            </tr>
            <tr>
                <td style="padding: 40px 30px;">
                    <h2 style="color: #333; margin-top: 0;">Hello,</h2>
                    <p style="color: #666; font-size: 16px; line-height: 1.6;">
                        We received a request to reset your password.
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0;">
                        <tr>
                            <td align="center">
                                <a href="{reset_link}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 15px 40px; text-decoration: none; border-radius: 50px; font-size: 16px; font-weight: bold; display: inline-block;">
                                    Reset My Password
                                </a>
                            </td>
                        </tr>
                    </table>
                    <p style="color: #999; font-size: 14px;">Link expires in 1 hour.</p>
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
                    <p style="color: #666; font-size: 16px;">Your booking has been confirmed!</p>
                    <table style="width: 100%; background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
                        <tr><td style="padding: 10px; color: #666;"><strong>Booking ID:</strong></td><td style="padding: 10px; color: #333;">{booking_data.get('tracking_id', 'N/A')}</td></tr>
                        <tr><td style="padding: 10px; color: #666;"><strong>Service:</strong></td><td style="padding: 10px; color: #333;">{booking_data.get('service_name', 'N/A')}</td></tr>
                        <tr><td style="padding: 10px; color: #666;"><strong>Date & Time:</strong></td><td style="padding: 10px; color: #333;">{booking_data.get('slot_start', 'N/A')}</td></tr>
                    </table>
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
                        <tr><td style="padding: 10px; color: #666;"><strong>Booking ID:</strong></td><td style="padding: 10px; color: #333;">{booking_data.get('tracking_id', 'N/A')}</td></tr>
                        <tr><td style="padding: 10px; color: #666;"><strong>Service:</strong></td><td style="padding: 10px; color: #333;">{booking_data.get('service_name', 'N/A')}</td></tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return await send_email(to_email, subject, body)