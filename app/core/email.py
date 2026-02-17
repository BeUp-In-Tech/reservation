import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using Gmail SMTP."""
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())

        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """Send password reset email."""
    
    subject = "Password Reset Request"
    body = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>You requested to reset your password.</p>
        <p>Use this token to reset your password:</p>
        <p style="background:#f0f0f0; padding:10px; font-family:monospace; word-break:break-all;">{reset_token}</p>
        <p><strong>Steps:</strong></p>
        <ol>
            <li>Go to: <a href="http://localhost:8000/docs">http://localhost:8000/docs</a></li>
            <li>Find POST /api/v1/admin/auth/reset-password</li>
            <li>Paste the token above with your new password</li>
        </ol>
        <p>This token expires in 1 hour.</p>
        <p>If you didn't request this, ignore this email.</p>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, body)