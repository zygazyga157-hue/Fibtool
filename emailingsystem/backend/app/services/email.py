"""
Email service for sending notifications and reports.
"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.payment import Payment
from app.models.user import User

settings = get_settings()


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: Optional[Path] = None
):
    """
    Send an email with optional attachment.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (HTML or plain text)
        attachment_path: Optional path to file attachment
    """
    # Create message
    message = MIMEMultipart()
    message["From"] = settings.FROM_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    
    # Add body
    message.attach(MIMEText(body, "html"))
    
    # Add attachment if provided
    if attachment_path and attachment_path.exists():
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {attachment_path.name}"
        )
        message.attach(part)
    
    # Send email
    try:
        # Skip actual sending if SMTP is not configured
        if not settings.SMTP_USER or settings.SMTP_USER == "your-email@gmail.com":
            print(f"[Email] SMTP not configured - would send to {to_email}: {subject}")
            return
        
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True
        )
        print(f"[Email] Sent to {to_email}: {subject}")
    except Exception as e:
        print(f"[Email] Failed to send to {to_email}: {str(e)}")
        # Don't raise in development - just log the error
        if settings.ENVIRONMENT == "production":
            raise


async def send_payment_confirmation(payment: Payment, db: Session):
    """
    Send payment confirmation email to user.
    
    Args:
        payment: Payment object
        db: Database session
    """
    try:
        user = db.query(User).filter(User.id == payment.user_id).first()
        if not user:
            print("[Email] User not found for payment confirmation")
            return
        
        subject = "Payment Confirmation - Fibtool"
        body = f"""
        <html>
            <body>
                <h2>Payment Confirmed</h2>
                <p>Dear {user.name or user.email},</p>
                <p>Thank you for your payment of ${payment.amount/100:.2f} {payment.currency}.</p>
                <p>Your Fibtool report will be delivered shortly.</p>
                <p>Payment ID: {payment.id}</p>
                <br>
                <p>Best regards,<br>The Fibtool Team</p>
            </body>
        </html>
        """
        
        await send_email(user.email, subject, body)
    except Exception as e:
        print(f"[Email] Error sending payment confirmation: {str(e)}")


async def send_report_delivery(
    user_email: str,
    symbol: str,
    timeframe: str,
    attachment_path: Path
):
    """
    Send plot report to user.
    
    Args:
        user_email: User email address
        symbol: Trading symbol
        timeframe: Chart timeframe
        attachment_path: Path to plot image
    """
    subject = f"Fibtool Report - {symbol} {timeframe}"
    body = f"""
    <html>
        <body>
            <h2>Your Fibtool Report</h2>
            <p>Please find attached your Fibtool analysis for {symbol} on {timeframe} timeframe.</p>
            <p>This report contains horizontal lines with confluence data from multiple technical indicators.</p>
            <br>
            <p>Best regards,<br>The Fibtool Team</p>
        </body>
    </html>
    """
    
    await send_email(user_email, subject, body, attachment_path)
