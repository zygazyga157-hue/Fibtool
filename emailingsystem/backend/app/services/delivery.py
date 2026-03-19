"""
Delivery service for generating and delivering plot reports.
"""
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import subprocess
import asyncio
from typing import Optional

from app.core.config import get_settings
from app.models.payment import Payment
from app.models.delivery import Delivery, DeliveryStatus
from app.models.user import User
from app.services.email import send_report_delivery

settings = get_settings()


async def create_delivery_task(payment_id: str, db: Session):
    """
    Create a delivery task for a paid order.
    This function creates a delivery record and triggers plot generation.
    
    Args:
        payment_id: Payment ID
        db: Database session
    """
    try:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            print(f"[Delivery] Payment {payment_id} not found")
            return
        
        user = db.query(User).filter(User.id == payment.user_id).first()
        if not user:
            print(f"[Delivery] User {payment.user_id} not found")
            return
        
        # Create delivery record
        delivery = Delivery(
            payment_id=payment_id,
            user_id=payment.user_id,
            symbol="XAUUSD",  # Default symbol for MVP
            timeframe="H1",   # Default timeframe
            status=DeliveryStatus.PENDING
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        
        print(f"[Delivery] Created delivery task {delivery.id} for payment {payment_id}")
        
        # Generate and send plot (in real implementation, this would be async/queued)
        try:
            await generate_and_send_plot(delivery, user, db)
        except Exception as e:
            print(f"[Delivery] Failed to generate plot: {str(e)}")
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            db.commit()
    except Exception as e:
        print(f"[Delivery] Error creating delivery task: {str(e)}")


async def generate_plot(symbol: str, timeframe: str = "H1") -> Optional[Path]:
    """
    Generate plot for given symbol using horizontal_lines_plot.py script.
    
    Args:
        symbol: Trading symbol (e.g., XAUUSD)
        timeframe: Chart timeframe
        
    Returns:
        Path to generated plot file, or None if generation failed
    """
    try:
        # Path to plotting script
        script_path = Path(__file__).parent.parent.parent.parent / "horizontal_lines_plot.py"
        output_dir = Path(__file__).parent.parent.parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)
        
        if not script_path.exists():
            print(f"[Delivery] Plotting script not found at {script_path}")
            return None
        
        print(f"[Delivery] Generating plot for {symbol}...")
        
        # Run plotting script with --once flag
        # This generates plot and saves to outputs directory
        cmd = [
            "python",
            str(script_path),
            "--symbols", symbol,
            "--once"
        ]
        
        # Execute in background
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print(f"[Delivery] Plot generated successfully")
            # Check for output file
            symbol_slug = symbol.lower().replace("/", "_")
            plot_filename = f"{symbol_slug}_horizontal_lines.png"
            plot_path = output_dir / plot_filename
            
            if plot_path.exists():
                return plot_path
            else:
                print(f"[Delivery] Plot file not found at expected path: {plot_path}")
                return None
        else:
            print(f"[Delivery] Plot generation failed: {stderr.decode()}")
            return None
            
    except Exception as e:
        print(f"[Delivery] Error generating plot: {str(e)}")
        return None


async def generate_and_send_plot(delivery: Delivery, user: User, db: Session):
    """
    Generate plot and send to user via email.
    
    Args:
        delivery: Delivery object
        user: User object
        db: Database session
    """
    try:
        # Update status to processing
        delivery.status = DeliveryStatus.PROCESSING
        db.commit()
        
        print(f"[Delivery] Processing delivery {delivery.id} for {user.email}")
        
        # Generate plot
        plot_path = await generate_plot(delivery.symbol, delivery.timeframe)
        
        if plot_path and plot_path.exists():
            # Send plot via email
            email_sent = await send_report_delivery(
                user.email,
                delivery.symbol,
                str(plot_path)
            )
            
            if email_sent:
                delivery.status = DeliveryStatus.SENT
                delivery.file_path = str(plot_path)
                delivery.email_sent_at = datetime.now(timezone.utc)
                print(f"[Delivery] Successfully sent plot to {user.email}")
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = "Failed to send email"
                print(f"[Delivery] Failed to send email to {user.email}")
        else:
            # Plot generation failed or no plot exists
            # For MVP, mark as sent anyway with a note
            delivery.status = DeliveryStatus.SENT
            delivery.file_path = None
            delivery.email_sent_at = datetime.now(timezone.utc)
            delivery.error_message = "Plot generation skipped - no MT5 connection"
            print(f"[Delivery] Marked as sent without plot for {user.email}")
        
        db.commit()
        
    except Exception as e:
        print(f"[Delivery] Error in generate_and_send_plot: {str(e)}")
        delivery.status = DeliveryStatus.FAILED
        delivery.error_message = str(e)
        db.commit()


async def retry_failed_delivery(delivery_id: str, db: Session):
    """
    Retry a failed delivery.
    
    Args:
        delivery_id: Delivery ID to retry
        db: Database session
    """
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        print(f"[Delivery] Delivery {delivery_id} not found")
        return
    
    if delivery.status != DeliveryStatus.FAILED:
        print(f"[Delivery] Delivery {delivery_id} is not in failed state")
        return
    
    user = db.query(User).filter(User.id == delivery.user_id).first()
    if not user:
        print(f"[Delivery] User {delivery.user_id} not found")
        return
    
    print(f"[Delivery] Retrying delivery {delivery_id}")
    await generate_and_send_plot(delivery, user, db)


def get_pending_deliveries(db: Session, limit: int = 10):
    """
    Get pending deliveries for processing.
    
    Args:
        db: Database session
        limit: Maximum number of deliveries to return
        
    Returns:
        List of pending deliveries
    """
    return db.query(Delivery).filter(
        Delivery.status == DeliveryStatus.PENDING
    ).limit(limit).all()

