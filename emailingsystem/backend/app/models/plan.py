"""
Plan model for subscription and one-off products.
"""
import uuid
from sqlalchemy import Column, String, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


def generate_uuid():
    """Generate a new UUID as string."""
    return str(uuid.uuid4())


class PlanType(str, enum.Enum):
    """Plan type enumeration."""
    ONE_OFF = "one-off"
    SUBSCRIPTION = "subscription"


class PlanInterval(str, enum.Enum):
    """Billing interval for subscriptions."""
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Plan(Base):
    """Pricing plan model."""
    __tablename__ = "plans"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    type = Column(SQLEnum(PlanType), nullable=False)
    price = Column(Integer, nullable=False)  # In cents/smallest unit
    currency = Column(String, default="USD")
    interval = Column(SQLEnum(PlanInterval), nullable=True)
    description = Column(String, nullable=True)
    
    # Relationships
    payments = relationship("Payment", back_populates="plan")
    subscriptions = relationship("Subscription", back_populates="plan")
