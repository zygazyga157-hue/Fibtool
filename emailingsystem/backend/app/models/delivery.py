"""
Delivery model for tracking plot generation and email sending.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum, Integer, Text
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


def generate_uuid():
    """Generate a new UUID as string."""
    return str(uuid.uuid4())


class DeliveryStatus(str, enum.Enum):
    """Delivery status enumeration."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class Delivery(Base):
    """Delivery tracking for plot generation and email sending."""
    __tablename__ = "deliveries"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("symbols.id"), nullable=True)  # Link to symbols table
    
    symbol = Column(String, nullable=True)  # Symbol code (e.g., XAUUSD)
    timeframe = Column(String, nullable=True)
    file_path = Column(String, nullable=True)  # Path to generated plot/report file
    report_content = Column(Text, nullable=True)  # Generated analysis text
    report_type = Column(String(50), default="confluence")  # Type of report
    
    status = Column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING)
    error_message = Column(String, nullable=True)
    email_sent_at = Column(DateTime, nullable=True)
    
    download_count = Column(Integer, default=0)  # Track downloads
    last_downloaded_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    payment = relationship("Payment", back_populates="deliveries")
    user = relationship("User", back_populates="deliveries")
