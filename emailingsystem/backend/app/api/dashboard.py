"""
Dashboard endpoint for authenticated users.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.delivery import Delivery
from app.schemas import PaymentResponse, SubscriptionResponse, DeliveryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get dashboard data for authenticated user."""
    # Get payments
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).order_by(Payment.created_at.desc()).all()
    
    # Get subscriptions
    subscriptions = db.query(Subscription).filter(Subscription.user_id == current_user.id).all()
    
    # Get deliveries
    deliveries = db.query(Delivery).filter(Delivery.user_id == current_user.id).order_by(Delivery.created_at.desc()).all()
    
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "is_admin": current_user.is_admin
        },
        "payments": [PaymentResponse.from_orm(p) for p in payments],
        "subscriptions": [SubscriptionResponse.from_orm(s) for s in subscriptions],
        "deliveries": [DeliveryResponse.from_orm(d) for d in deliveries]
    }
