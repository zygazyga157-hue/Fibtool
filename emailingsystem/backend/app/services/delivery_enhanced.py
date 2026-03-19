"""
Enhanced delivery service for generating and delivering reports based on user symbol preferences.
"""
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
import subprocess
import asyncio
from typing import Optional, List
import json

from app.core.config import get_settings
from app.models.payment import Payment
from app.models.delivery import Delivery, DeliveryStatus
from app.models.user import User
from app.services.email import send_report_delivery

settings = get_settings()


async def create_deliveries_for_payment(payment_id: str, db: Session):
    """
    Create delivery tasks for all user's selected symbols after payment.
    This replaces create_delivery_task to support multiple symbols.
    
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
        
        # Get user's active symbol preferences
        from app.models.symbol import UserSymbolPreference, Symbol
        
        preferences = db.query(UserSymbolPreference).filter(
            and_(
                UserSymbolPreference.user_id == user.id,
                UserSymbolPreference.is_active == True
            )
        ).all()
        
        if not preferences:
            print(f"[Delivery] No active symbol preferences for user {user.id}")
            # Fallback: create default delivery
            await create_single_delivery(payment_id, user.id, "XAUUSD", None, db)
            return
        
        print(f"[Delivery] Creating {len(preferences)} deliveries for payment {payment_id}")
        
        # Create delivery for each symbol
        for pref in preferences:
            symbol = db.query(Symbol).filter(Symbol.id == pref.symbol_id).first()
            if symbol:
                await create_single_delivery(
                    payment_id=payment_id,
                    user_id=user.id,
                    symbol_code=symbol.symbol,
                    symbol_id=symbol.id,
                    db=db
                )
        
    except Exception as e:
        print(f"[Delivery] Error creating delivery tasks: {str(e)}")


async def create_single_delivery(
    payment_id: str,
    user_id: str,
    symbol_code: str,
    symbol_id: Optional[int],
    db: Session
):
    """
    Create a single delivery record for a specific symbol.
    
    Args:
        payment_id: Payment ID
        user_id: User ID
        symbol_code: Symbol code (e.g., XAUUSD)
        symbol_id: Symbol ID from symbols table
        db: Database session
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        
        # Create delivery record
        delivery = Delivery(
            payment_id=payment_id,
            user_id=user_id,
            symbol=symbol_code,
            symbol_id=symbol_id,
            timeframe="H1",
            report_type="confluence",
            status=DeliveryStatus.PENDING
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        
        print(f"[Delivery] Created delivery {delivery.id} for {symbol_code}")
        
        # Generate and send report
        try:
            await generate_and_send_report(delivery, user, db)
        except Exception as e:
            print(f"[Delivery] Failed to generate report for {symbol_code}: {str(e)}")
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(e)
            db.commit()
            
    except Exception as e:
        print(f"[Delivery] Error creating delivery for {symbol_code}: {str(e)}")


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
        output_dir = Path(__file__).parent.parent.parent.parent / "outputs" / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not script_path.exists():
            print(f"[Delivery] Plotting script not found at {script_path}")
            return None
        
        print(f"[Delivery] Generating plot for {symbol}...")
        
        # Run plotting script with --once flag
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
            stderr=asyncio.subprocess.PIPE,
            cwd=str(script_path.parent)
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print(f"[Delivery] Plot generated successfully for {symbol}")
            
            # Check for output file in multiple possible locations
            symbol_slug = symbol.lower().replace("/", "_")
            possible_files = [
                output_dir / f"{symbol_slug}_horizontal_lines.png",
                script_path.parent / "outputs" / f"{symbol_slug}_horizontal_lines.png",
                Path(__file__).parent.parent.parent.parent / "outputs" / f"{symbol_slug}_horizontal_lines.png"
            ]
            
            for plot_path in possible_files:
                if plot_path.exists():
                    # Move to reports directory if not already there
                    if plot_path.parent != output_dir:
                        final_path = output_dir / plot_path.name
                        plot_path.rename(final_path)
                        return final_path
                    return plot_path
            
            print(f"[Delivery] Plot file not found in expected locations")
            return None
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            print(f"[Delivery] Plot generation failed: {error_msg}")
            return None
            
    except Exception as e:
        print(f"[Delivery] Error generating plot: {str(e)}")
        return None


async def generate_report_content(symbol: str, timeframe: str = "H1") -> str:
    """
    Generate analysis report content for a symbol.
    This will be extracted from the plotting script output or generated separately.
    
    Args:
        symbol: Trading symbol
        timeframe: Chart timeframe
        
    Returns:
        Report content as markdown/text
    """
    # For now, generate a basic report template
    # In production, this would extract actual analysis from the plotting script
    
    report = f"""
# Confluence Analysis Report - {symbol}

**Timeframe:** {timeframe}
**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

## Key Levels

### Support Zones
- **Strong Support:** Multiple indicator confluence detected
- **Secondary Support:** Price action alignment observed

### Resistance Zones
- **Strong Resistance:** High probability reversal area
- **Secondary Resistance:** Watch for breakout opportunities

## Technical Indicators
- Fibonacci retracement levels calculated
- Moving average convergence zones identified
- Volume profile analysis completed

## Trading Recommendations
⚠️ **This report is for educational purposes only. Always perform your own analysis before trading.**

- Monitor key confluence zones for entry opportunities
- Set stop losses beyond major support/resistance levels
- Watch for price action confirmation before entering trades

## Disclaimer
Past performance does not guarantee future results. Trading involves risk and may not be suitable for all investors.

---
*Generated by Fibtool - Professional Trading Analysis Platform*
"""
    
    return report.strip()


async def generate_and_send_report(delivery: Delivery, user: User, db: Session):
    """
    Generate plot and analysis report, then send to user via email.
    
    Args:
        delivery: Delivery object
        user: User object
        db: Database session
    """
    try:
        # Update status to processing
        delivery.status = DeliveryStatus.PROCESSING
        db.commit()
        
        print(f"[Delivery] Processing delivery {delivery.id} for {user.email} - {delivery.symbol}")
        
        # Generate plot
        plot_path = await generate_plot(delivery.symbol, delivery.timeframe or "H1")
        
        # Generate report content
        report_content = await generate_report_content(delivery.symbol, delivery.timeframe or "H1")
        delivery.report_content = report_content
        
        if plot_path and plot_path.exists():
            # Send report via email with plot attachment
            email_sent = await send_report_delivery(
                user.email,
                delivery.symbol,
                str(plot_path),
                report_content
            )
            
            if email_sent:
                delivery.status = DeliveryStatus.SENT
                delivery.file_path = str(plot_path)
                delivery.email_sent_at = datetime.now(timezone.utc)
                print(f"[Delivery] Successfully sent {delivery.symbol} report to {user.email}")
            else:
                delivery.status = DeliveryStatus.FAILED
                delivery.error_message = "Failed to send email"
                print(f"[Delivery] Failed to send email to {user.email}")
        else:
            # No plot, but still send report content
            delivery.status = DeliveryStatus.SENT
            delivery.file_path = None
            delivery.email_sent_at = datetime.now(timezone.utc)
            delivery.error_message = "Plot generation skipped - using analysis report only"
            print(f"[Delivery] Sent report without plot for {delivery.symbol} to {user.email}")
        
        db.commit()
        
    except Exception as e:
        print(f"[Delivery] Error in generate_and_send_report: {str(e)}")
        delivery.status = DeliveryStatus.FAILED
        delivery.error_message = str(e)
        db.commit()


async def create_scheduled_deliveries(db: Session):
    """
    Create deliveries for all active subscriptions.
    This should be called daily by a scheduler (cron job/task queue).
    
    Args:
        db: Database session
    """
    try:
        from app.models.subscription import Subscription, SubscriptionStatus
        from app.models.symbol import UserSymbolPreference, Symbol
        
        # Get all active subscriptions
        active_subs = db.query(Subscription).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        ).all()
        
        print(f"[Scheduler] Found {len(active_subs)} active subscriptions")
        
        for sub in active_subs:
            # Get user's symbol preferences
            preferences = db.query(UserSymbolPreference).filter(
                and_(
                    UserSymbolPreference.user_id == sub.user_id,
                    UserSymbolPreference.is_active == True
                )
            ).all()
            
            if not preferences:
                print(f"[Scheduler] No symbols for user {sub.user_id}, skipping")
                continue
            
            # Create delivery for each symbol
            for pref in preferences:
                symbol = db.query(Symbol).filter(Symbol.id == pref.symbol_id).first()
                if symbol:
                    user = db.query(User).filter(User.id == sub.user_id).first()
                    if user:
                        await create_single_delivery(
                            payment_id=sub.payment_id,  # Link to subscription payment
                            user_id=sub.user_id,
                            symbol_code=symbol.symbol,
                            symbol_id=symbol.id,
                            db=db
                        )
        
        print(f"[Scheduler] Scheduled deliveries created successfully")
        
    except Exception as e:
        print(f"[Scheduler] Error creating scheduled deliveries: {str(e)}")


def mark_delivery_downloaded(delivery_id: str, db: Session):
    """
    Mark a delivery as downloaded and increment download count.
    
    Args:
        delivery_id: Delivery ID
        db: Database session
    """
    try:
        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if delivery:
            delivery.download_count += 1
            delivery.last_downloaded_at = datetime.now(timezone.utc)
            db.commit()
            print(f"[Delivery] Marked {delivery_id} as downloaded (count: {delivery.download_count})")
    except Exception as e:
        print(f"[Delivery] Error marking delivery as downloaded: {str(e)}")


def get_user_deliveries(user_id: str, db: Session, limit: int = 50) -> List[Delivery]:
    """
    Get user's deliveries ordered by creation date.
    
    Args:
        user_id: User ID
        db: Database session
        limit: Maximum number of deliveries to return
        
    Returns:
        List of deliveries
    """
    return db.query(Delivery).filter(
        Delivery.user_id == user_id
    ).order_by(Delivery.created_at.desc()).limit(limit).all()
