"""
Admin endpoints for system management and monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.delivery import Delivery, DeliveryStatus
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan
from app.services.delivery import retry_failed_delivery, get_pending_deliveries

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)):
    """Dependency to require admin access."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/dashboard")
async def admin_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive admin dashboard statistics.
    """
    # User statistics
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    new_users_today = db.query(User).filter(
        User.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    ).count()
    new_users_week = db.query(User).filter(
        User.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
    ).count()
    
    # Payment statistics
    total_payments = db.query(Payment).count()
    paid_payments = db.query(Payment).filter(Payment.status == PaymentStatus.PAID).count()
    pending_payments = db.query(Payment).filter(Payment.status == PaymentStatus.PENDING).count()
    failed_payments = db.query(Payment).filter(Payment.status == PaymentStatus.FAILED).count()
    
    # Revenue calculation
    total_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.PAID
    ).scalar() or 0
    
    revenue_today = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.PAID,
        Payment.paid_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
    ).scalar() or 0
    
    revenue_week = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.PAID,
        Payment.paid_at >= datetime.now(timezone.utc) - timedelta(days=7)
    ).scalar() or 0
    
    revenue_month = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.PAID,
        Payment.paid_at >= datetime.now(timezone.utc) - timedelta(days=30)
    ).scalar() or 0
    
    # Subscription statistics
    total_subscriptions = db.query(Subscription).count()
    active_subscriptions = db.query(Subscription).filter(
        Subscription.status == SubscriptionStatus.ACTIVE
    ).count()
    
    # Delivery statistics
    total_deliveries = db.query(Delivery).count()
    pending_deliveries = db.query(Delivery).filter(
        Delivery.status == DeliveryStatus.PENDING
    ).count()
    processing_deliveries = db.query(Delivery).filter(
        Delivery.status == DeliveryStatus.PROCESSING
    ).count()
    sent_deliveries = db.query(Delivery).filter(
        Delivery.status == DeliveryStatus.SENT
    ).count()
    failed_deliveries = db.query(Delivery).filter(
        Delivery.status == DeliveryStatus.FAILED
    ).count()
    
    # Plan statistics
    plan_stats = db.query(
        Plan.name,
        func.count(Payment.id).label('purchase_count'),
        func.sum(Payment.amount).label('revenue')
    ).join(Payment).filter(
        Payment.status == PaymentStatus.PAID
    ).group_by(Plan.id, Plan.name).all()
    
    # Recent activity
    recent_payments = db.query(Payment).order_by(desc(Payment.created_at)).limit(5).all()
    recent_deliveries = db.query(Delivery).order_by(desc(Delivery.created_at)).limit(5).all()
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "new_today": new_users_today,
            "new_this_week": new_users_week
        },
        "payments": {
            "total": total_payments,
            "paid": paid_payments,
            "pending": pending_payments,
            "failed": failed_payments,
            "success_rate": f"{(paid_payments/total_payments*100) if total_payments > 0 else 0:.1f}%"
        },
        "revenue": {
            "total": total_revenue / 100,
            "today": revenue_today / 100,
            "this_week": revenue_week / 100,
            "this_month": revenue_month / 100,
            "currency": "USD"
        },
        "subscriptions": {
            "total": total_subscriptions,
            "active": active_subscriptions,
            "inactive": total_subscriptions - active_subscriptions
        },
        "deliveries": {
            "total": total_deliveries,
            "pending": pending_deliveries,
            "processing": processing_deliveries,
            "sent": sent_deliveries,
            "failed": failed_deliveries,
            "success_rate": f"{(sent_deliveries/total_deliveries*100) if total_deliveries > 0 else 0:.1f}%"
        },
        "plans": [
            {
                "name": stat[0],
                "purchases": stat[1],
                "revenue": (stat[2] or 0) / 100
            }
            for stat in plan_stats
        ],
        "recent_activity": {
            "payments": [
                {
                    "id": p.id,
                    "amount": p.amount / 100,
                    "status": p.status.value,
                    "user_id": p.user_id,
                    "created_at": p.created_at.isoformat()
                }
                for p in recent_payments
            ],
            "deliveries": [
                {
                    "id": d.id,
                    "symbol": d.symbol,
                    "status": d.status.value,
                    "user_id": d.user_id,
                    "created_at": d.created_at.isoformat()
                }
                for d in recent_deliveries
            ]
        }
    }


@router.get("/users")
async def list_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users with search and pagination.
    """
    query = db.query(User)
    
    if search:
        query = query.filter(
            (User.email.ilike(f"%{search}%")) | 
            (User.name.ilike(f"%{search}%"))
        )
    
    total = query.count()
    users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat(),
                "payment_count": len(u.payments),
                "subscription_count": len([s for s in u.subscriptions if s.status == SubscriptionStatus.ACTIVE])
            }
            for u in users
        ]
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(404, "User not found")
    
    # Calculate total spent
    total_spent = db.query(func.sum(Payment.amount)).filter(
        Payment.user_id == user_id,
        Payment.status == PaymentStatus.PAID
    ).scalar() or 0
    
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
        "statistics": {
            "total_payments": len(user.payments),
            "paid_payments": len([p for p in user.payments if p.status == PaymentStatus.PAID]),
            "total_spent": total_spent / 100,
            "active_subscriptions": len([s for s in user.subscriptions if s.status == SubscriptionStatus.ACTIVE]),
            "total_deliveries": len(user.deliveries),
            "successful_deliveries": len([d for d in user.deliveries if d.status == DeliveryStatus.SENT])
        },
        "payments": [
            {
                "id": p.id,
                "amount": p.amount / 100,
                "status": p.status.value,
                "created_at": p.created_at.isoformat(),
                "paid_at": p.paid_at.isoformat() if p.paid_at else None
            }
            for p in sorted(user.payments, key=lambda x: x.created_at, reverse=True)[:10]
        ],
        "subscriptions": [
            {
                "id": s.id,
                "plan_id": s.plan_id,
                "status": s.status.value,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None
            }
            for s in user.subscriptions
        ],
        "deliveries": [
            {
                "id": d.id,
                "symbol": d.symbol,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
                "error_message": d.error_message
            }
            for d in sorted(user.deliveries, key=lambda x: x.created_at, reverse=True)[:10]
        ]
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    is_active: Optional[bool] = None,
    is_admin: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update user account (activate/deactivate, grant/revoke admin).
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(404, "User not found")
    
    if is_active is not None:
        user.is_active = is_active
    
    if is_admin is not None:
        user.is_admin = is_admin
    
    db.commit()
    
    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "message": "User updated successfully"
    }


@router.get("/deliveries/pending")
async def list_pending_deliveries(
    limit: int = 10,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List pending deliveries.
    """
    deliveries = get_pending_deliveries(db, limit=limit)
    
    return {
        "total": len(deliveries),
        "deliveries": [
            {
                "id": d.id,
                "payment_id": d.payment_id,
                "user_id": d.user_id,
                "user_email": d.user.email if d.user else None,
                "symbol": d.symbol,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
                "error_message": d.error_message
            }
            for d in deliveries
        ]
    }


@router.get("/deliveries/failed")
async def list_failed_deliveries(
    limit: int = 10,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List failed deliveries.
    """
    deliveries = db.query(Delivery).filter(
        Delivery.status == DeliveryStatus.FAILED
    ).order_by(desc(Delivery.created_at)).limit(limit).all()
    
    return {
        "total": len(deliveries),
        "deliveries": [
            {
                "id": d.id,
                "payment_id": d.payment_id,
                "user_id": d.user_id,
                "user_email": d.user.email if d.user else None,
                "symbol": d.symbol,
                "status": d.status.value,
                "error_message": d.error_message,
                "created_at": d.created_at.isoformat()
            }
            for d in deliveries
        ]
    }


@router.post("/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Retry a failed delivery.
    """
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    
    if not delivery:
        raise HTTPException(404, "Delivery not found")
    
    if delivery.status != DeliveryStatus.FAILED:
        raise HTTPException(400, f"Delivery is in {delivery.status} state, not FAILED")
    
    # Trigger retry
    await retry_failed_delivery(delivery_id, db)
    
    # Refresh delivery
    db.refresh(delivery)
    
    return {
        "message": "Delivery retry triggered",
        "delivery_id": delivery_id,
        "status": delivery.status.value
    }


@router.get("/payments")
async def list_payments(
    skip: int = 0,
    limit: int = 50,
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all payments with filtering and pagination.
    """
    query = db.query(Payment)
    
    if status_filter:
        query = query.filter(Payment.status == status_filter.upper())
    
    total = query.count()
    payments = query.order_by(desc(Payment.created_at)).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "payments": [
            {
                "id": p.id,
                "user_id": p.user_id,
                "user_email": p.user.email if p.user else None,
                "amount": p.amount / 100,
                "currency": p.currency,
                "status": p.status.value,
                "provider_reference": p.provider_reference,
                "created_at": p.created_at.isoformat(),
                "paid_at": p.paid_at.isoformat() if p.paid_at else None
            }
            for p in payments
        ]
    }


@router.get("/stats/revenue")
async def revenue_stats(
    days: int = 30,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get daily revenue statistics for the last N days.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get daily revenue
    daily_revenue = db.query(
        func.date(Payment.paid_at).label('date'),
        func.sum(Payment.amount).label('revenue'),
        func.count(Payment.id).label('count')
    ).filter(
        Payment.status == PaymentStatus.PAID,
        Payment.paid_at >= start_date
    ).group_by(func.date(Payment.paid_at)).all()
    
    return {
        "period_days": days,
        "daily_revenue": [
            {
                "date": str(r[0]),
                "revenue": (r[1] or 0) / 100,
                "transaction_count": r[2]
            }
            for r in daily_revenue
        ]
    }

