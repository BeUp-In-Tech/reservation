import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import asyncio


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP."""
    try:
        # ✅ Run blocking SMTP in thread pool to avoid async issues
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _send_email_sync, to_email, subject, body)
        return result
    except Exception as e:
        print(f"Email error: {e}")
        return False


def _send_email_sync(to_email: str, subject: str, body: str) -> bool:
    """Synchronous email sending - runs in thread pool."""
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())

        print(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email."""

    reset_link = f"https://reservation-xynh.onrender.com/api/v1/admin/auth/reset-password?token={reset_token}"

    subject = "Password Reset Request"
    body = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>You requested to reset your password.</p>
        <p>Click the button below to reset your password:</p>
        <a href="{reset_link}" style="background:#4CAF50; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">
            Reset Password
        </a>
        <p>Or copy this link:</p>
        <p style="background:#f0f0f0; padding:10px; font-family:monospace; word-break:break-all;">
            {reset_link}
        </p>
        <p>This link expires in 1 hour.</p>
        <p>If you didn't request this, ignore this email.</p>
    </body>
    </html>
    """

    return await send_email(to_email, subject, body)