"""
Payment model for tracking transactions.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


def generate_uuid():
    """Generate a new UUID as string."""
    return str(uuid.uuid4())


class PaymentStatus(str, enum.Enum):
    """Payment status enumeration."""
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Payment(Base):
    """Payment transaction model."""
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=False)
    
    amount = Column(Integer, nullable=False)
    currency = Column(String, default="USD")
    status = Column(SQLEnum(PaymentStatus), default=PaymentStatus.PENDING)
    
    provider = Column(String, default="paynow")
    provider_reference = Column(String, unique=True, nullable=True, index=True)
    idempotency_key = Column(String, unique=True, nullable=True, index=True)
    
    payload = Column(JSON, nullable=True)  # Raw provider response
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="payments")
    plan = relationship("Plan", back_populates="payments")
    deliveries = relationship("Delivery", back_populates="payment")
