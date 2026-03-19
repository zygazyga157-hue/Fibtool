"""
Checkout and payment endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.plan import Plan
from app.models.payment import Payment, PaymentStatus
from app.schemas import CheckoutRequest, CheckoutResponse, PaymentResponse
from app.services.paynow import create_paynow_transaction

router = APIRouter(tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a payment request and return payment URL."""
    # Verify plan exists
    plan = db.query(Plan).filter(Plan.id == request.plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Generate idempotency key
    idempotency_key = str(uuid.uuid4())
    
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        plan_id=plan.id,
        amount=plan.price,
        currency=plan.currency,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    # Create PayNow transaction
    try:
        payment_url, paynow_reference = await create_paynow_transaction(
            payment_id=payment.id,
            amount=plan.price,
            email=current_user.email,
            description=f"{plan.name} - {current_user.email}"
        )
        
        # Update payment with provider reference
        payment.provider_reference = paynow_reference
        db.commit()
        
        return CheckoutResponse(
            payment_id=payment.id,
            payment_url=payment_url
        )
    except Exception as e:
        # Mark payment as failed
        payment.status = PaymentStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(e)}"
        )


@router.post("/checkout-inline")
async def checkout_inline(
    request: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a payment request and return form data for in-app payment.
    This allows payment to be completed within the app without redirect.
    """
    # Verify plan exists
    plan = db.query(Plan).filter(Plan.id == request.plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found"
        )
    
    # Generate idempotency key
    idempotency_key = str(uuid.uuid4())
    
    # Create payment record
    payment = Payment(
        user_id=current_user.id,
        plan_id=plan.id,
        amount=plan.price,
        currency=plan.currency,
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    # Create PayNow transaction and get form data
    try:
        from app.services.paynow import create_paynow_inline_data
        
        form_data = await create_paynow_inline_data(
            payment_id=payment.id,
            amount=plan.price,
            email=current_user.email,
            description=f"{plan.name} - {current_user.email}"
        )
        
        # Update payment with provider reference
        payment.provider_reference = form_data["reference"]
        db.commit()
        
        return {
            "payment_id": payment.id,
            "form_data": form_data,
            "amount": float(plan.price),
            "currency": plan.currency,
            "plan_name": plan.name
        }
    except Exception as e:
        # Mark payment as failed
        payment.status = PaymentStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(e)}"
        )


@router.get("/payment/{payment_id}", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get payment status."""
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    return payment
