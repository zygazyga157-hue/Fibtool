"""
Webhook endpoints for payment notifications.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict

from app.core.database import get_db
from app.models.payment import Payment, PaymentStatus
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.plan import Plan, PlanType
from app.services.paynow import verify_webhook_signature
from app.services.email import send_payment_confirmation
from app.services.delivery_enhanced import create_deliveries_for_payment

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/paynow")
async def paynow_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Handle PayNow webhook notifications.
    This endpoint is called by PayNow when payment status changes.
    
    PayNow sends POST data in format:
    - reference: Your payment reference
    - paynowreference: PayNow transaction ID
    - amount: Payment amount
    - status: Payment status (Paid, Failed, Cancelled, etc.)
    - pollurl: URL to poll for status
    - hash: Security hash
    """
    try:
        # Get form data from PayNow
        form_data = await request.form()
        webhook_data: Dict[str, str] = dict(form_data)
        
        print(f"[Webhook] Received PayNow webhook: {webhook_data}")
        
        # Extract webhook data
        reference = webhook_data.get("reference")
        paynow_reference = webhook_data.get("paynowreference")
        status_str = webhook_data.get("status", "").lower()
        amount = webhook_data.get("amount")
        poll_url = webhook_data.get("pollurl")
        
        if not reference:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing payment reference"
            )
        
        # Verify webhook hash
        is_valid = verify_webhook_signature(webhook_data)
        if not is_valid:
            print(f"[Webhook] WARNING: Invalid hash for reference {reference}")
            # Continue processing but log the warning
        
        # Find payment by reference (our payment ID)
        payment = db.query(Payment).filter(Payment.id == reference).first()
        
        if not payment:
            print(f"[Webhook] Payment not found: {reference}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {reference}"
            )
        
        # Update PayNow reference if provided
        if paynow_reference and not payment.provider_reference:
            payment.provider_reference = paynow_reference
        
        # Store full webhook payload
        payment.payload = webhook_data
        
        # Check idempotency - skip if already processed
        if payment.status == PaymentStatus.PAID:
            print(f"[Webhook] Payment {reference} already processed")
            db.commit()
            return {"status": "already_processed", "payment_id": payment.id}
        
        # Update payment status based on PayNow status
        if status_str == "paid":
            print(f"[Webhook] Payment {reference} marked as PAID")
            payment.status = PaymentStatus.PAID
            payment.paid_at = datetime.now(timezone.utc)
            
            # Get plan to determine if subscription should be created
            plan = db.query(Plan).filter(Plan.id == payment.plan_id).first()
            
            if plan:
                # Create subscription if plan is subscription type
                if plan.type == PlanType.SUBSCRIPTION:
                    # Check if subscription already exists
                    existing_sub = db.query(Subscription).filter(
                        Subscription.user_id == payment.user_id,
                        Subscription.plan_id == plan.id,
                        Subscription.status == SubscriptionStatus.ACTIVE
                    ).first()
                    
                    if not existing_sub:
                        subscription = Subscription(
                            user_id=payment.user_id,
                            plan_id=plan.id,
                            status=SubscriptionStatus.ACTIVE
                        )
                        db.add(subscription)
                        print(f"[Webhook] Created subscription for user {payment.user_id}")
            
            db.commit()
            
            # Trigger delivery task (async) - creates deliveries for all user's selected symbols
            print(f"[Webhook] Triggering deliveries for payment {reference}")
            await create_deliveries_for_payment(payment.id, db)
            
            # Send confirmation email
            try:
                await send_payment_confirmation(payment, db)
            except Exception as e:
                print(f"[Webhook] Failed to send confirmation email: {str(e)}")
            
            return {
                "status": "success",
                "payment_id": payment.id,
                "message": "Payment processed successfully"
            }
        
        elif status_str in ["failed", "cancelled"]:
            print(f"[Webhook] Payment {reference} marked as {status_str.upper()}")
            payment.status = PaymentStatus.FAILED if status_str == "failed" else PaymentStatus.CANCELLED
            db.commit()
            return {
                "status": status_str,
                "payment_id": payment.id,
                "message": f"Payment {status_str}"
            }
        
        else:
            # Other statuses (sent, delivered, awaiting delivery, etc.)
            print(f"[Webhook] Payment {reference} status: {status_str}")
            payment.status = PaymentStatus.PENDING
            db.commit()
            return {
                "status": "pending",
                "payment_id": payment.id,
                "paynow_status": status_str
            }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Webhook] Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing error: {str(e)}"
        )


@router.get("/paynow/test")
async def test_webhook(
    reference: str,
    paynow_status: str = "paid",
    db: Session = Depends(get_db)
):
    """
    Test endpoint to simulate PayNow webhook for development.
    
    Usage: GET /api/v1/webhooks/paynow/test?reference=PAYMENT_ID&paynow_status=paid
    """
    # Simulate webhook data
    test_data = {
        "reference": reference,
        "paynowreference": f"TEST-{reference[:8]}",
        "amount": "20.00",
        "status": paynow_status,
        "pollurl": f"https://www.paynow.co.zw/interface/querytransaction?guid={reference}",
        "hash": "test_hash"
    }
    
    print(f"[Webhook Test] Simulating {paynow_status} webhook for {reference}")
    
    # Find payment
    payment = db.query(Payment).filter(Payment.id == reference).first()
    if not payment:
        raise HTTPException(404, f"Payment {reference} not found")
    
    # Update payment
    if paynow_status.lower() == "paid":
        payment.status = PaymentStatus.PAID
        payment.paid_at = datetime.now(timezone.utc)
        payment.provider_reference = test_data["paynowreference"]
        payment.payload = test_data
        
        # Get plan
        plan = db.query(Plan).filter(Plan.id == payment.plan_id).first()
        
        if plan and plan.type == PlanType.SUBSCRIPTION:
            subscription = Subscription(
                user_id=payment.user_id,
                plan_id=plan.id,
                status=SubscriptionStatus.ACTIVE
            )
            db.add(subscription)
        
        db.commit()
        
        # Trigger delivery - creates deliveries for all user's selected symbols
        await create_deliveries_for_payment(payment.id, db)
        
        return {
            "status": "success",
            "message": f"Test webhook processed - Payment {reference} marked as PAID",
            "payment_id": payment.id
        }
    
    return {"status": "test_completed", "reference": reference}

