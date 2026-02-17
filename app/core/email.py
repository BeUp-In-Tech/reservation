import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import asyncio


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP."""
    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _send_email_sync, to_email, subject, body),
            timeout=30.0  # 30 second timeout
        )
        return result
    except asyncio.TimeoutError:
        print(f"Email timeout: Failed to send to {to_email} within 30 seconds")
        return False
    except Exception as e:
        print(f"Email error: {e}")
        return False


def _send_email_sync(to_email: str, subject: str, body: str) -> bool:
    """Synchronous email sending - runs in thread pool."""
    try:
        print(f"Attempting to send email to {to_email}")
        print(f"SMTP_HOST: {settings.SMTP_HOST}")
        print(f"SMTP_PORT: {settings.SMTP_PORT}")
        print(f"SMTP_USER: {settings.SMTP_USER}")
        print(f"FROM_EMAIL: {settings.FROM_EMAIL}")
        
        if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            print("Email error: SMTP settings not configured")
            return False

        msg = MIMEMultipart()
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        print("Connecting to SMTP server...")
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            print("Connected. Starting TLS...")
            server.ehlo()
            server.starttls()
            server.ehlo()
            print("Logging in...")
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            print("Sending email...")
            server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())

        print(f"Email sent successfully to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"Email auth error: {e} - Check SMTP_PASSWORD (App Password)")
        return False
    except smtplib.SMTPException as e:
        print(f"SMTP error: {e}")
        return False
    except Exception as e:
        print(f"Email error: {type(e).__name__}: {e}")
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