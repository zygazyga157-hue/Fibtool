"""
Pydantic schemas for API requests and responses.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# User schemas
class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Schema for user response."""
    id: str
    email: str
    name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


# Plan schemas
class PlanResponse(BaseModel):
    """Schema for plan response."""
    id: str
    name: str
    type: str
    price: int
    currency: str
    interval: Optional[str]
    description: Optional[str]
    
    class Config:
        from_attributes = True


# Payment schemas
class CheckoutRequest(BaseModel):
    """Schema for checkout request."""
    plan_id: str
    return_url: str
    customer_email: Optional[EmailStr] = None


class CheckoutResponse(BaseModel):
    """Schema for checkout response."""
    payment_id: str
    payment_url: str


class PaymentResponse(BaseModel):
    """Schema for payment response."""
    id: str
    user_id: str
    plan_id: str
    amount: int
    currency: str
    status: str
    provider: str
    created_at: datetime
    paid_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# Subscription schemas
class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""
    id: str
    user_id: str
    plan_id: str
    status: str
    started_at: datetime
    cancelled_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# Delivery schemas
class DeliveryRequest(BaseModel):
    """Schema for ad-hoc delivery request."""
    symbol: str
    timeframe: str
    email: Optional[EmailStr] = None


class DeliveryResponse(BaseModel):
    """Schema for delivery response."""
    id: str
    payment_id: str
    user_id: str
    symbol: Optional[str]
    timeframe: Optional[str]
    status: str
    email_sent_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True
