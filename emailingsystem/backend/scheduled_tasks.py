"""
Scheduled Tasks Runner for FibTool Email System

This script handles scheduled tasks like:
1. Creating daily report deliveries for active subscriptions
2. Cleaning up old report files (>30 days)

Run this script using a cron job or task scheduler:
- Linux/Mac: Add to crontab
  0 1 * * * /path/to/python /path/to/scheduled_tasks.py
  
- Windows: Use Task Scheduler
  - Action: Start a program
  - Program: python.exe
  - Arguments: C:\path\to\scheduled_tasks.py
  - Trigger: Daily at 1:00 AM
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.services.delivery_enhanced import create_scheduled_deliveries
from app.models.delivery import Delivery

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(backend_dir / 'logs' / 'scheduled_tasks.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def create_daily_deliveries():
    """
    Create deliveries for all active subscriptions.
    This should run once per day.
    """
    logger.info("Starting daily delivery creation task...")
    db = SessionLocal()
    try:
        count = await create_scheduled_deliveries(db)
        logger.info(f"✅ Created {count} deliveries for active subscriptions")
        return count
    except Exception as e:
        logger.error(f"❌ Failed to create scheduled deliveries: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


async def cleanup_old_reports(days: int = 30):
    """
    Delete report files older than specified days and update database.
    Keeps report_content in database but removes physical files.
    
    Args:
        days: Number of days to keep reports (default 30)
    """
    logger.info(f"Starting cleanup of reports older than {days} days...")
    db = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find old deliveries with files
        old_deliveries = db.query(Delivery).filter(
            Delivery.created_at < cutoff_date,
            Delivery.file_path.isnot(None)
        ).all()
        
        deleted_count = 0
        error_count = 0
        
        for delivery in old_deliveries:
            try:
                # Check if file exists and delete it
                if delivery.file_path:
                    file_path = Path(delivery.file_path)
                    if file_path.exists():
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted file: {delivery.file_path}")
                    
                    # Update database - keep record but remove file_path
                    delivery.file_path = None
                    db.commit()
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Failed to delete file {delivery.file_path}: {str(e)}")
                continue
        
        logger.info(f"✅ Cleanup complete: {deleted_count} files deleted, {error_count} errors")
        return deleted_count, error_count
        
    except Exception as e:
        logger.error(f"❌ Cleanup task failed: {str(e)}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


async def send_pending_emails():
    """
    Retry sending emails for deliveries that failed or are still pending.
    Only retries deliveries created within last 24 hours.
    """
    logger.info("Checking for pending email deliveries...")
    db = SessionLocal()
    try:
        from app.services.email import send_delivery_email
        
        # Find deliveries from last 24 hours that need email retry
        cutoff = datetime.utcnow() - timedelta(hours=24)
        pending_deliveries = db.query(Delivery).filter(
            Delivery.created_at > cutoff,
            Delivery.status == "SENT",  # Report was generated
            Delivery.email_sent_at.is_(None),  # But email wasn't sent
            Delivery.file_path.isnot(None)  # And file exists
        ).all()
        
        success_count = 0
        fail_count = 0
        
        for delivery in pending_deliveries:
            try:
                await send_delivery_email(
                    to_email=delivery.user.email,
                    symbol=delivery.symbol,
                    file_path=delivery.file_path,
                    report_content=delivery.report_content
                )
                delivery.email_sent_at = datetime.utcnow()
                db.commit()
                success_count += 1
                logger.info(f"✅ Sent email for delivery {delivery.id}")
            except Exception as e:
                fail_count += 1
                logger.error(f"❌ Failed to send email for delivery {delivery.id}: {str(e)}")
                continue
        
        logger.info(f"Email retry complete: {success_count} sent, {fail_count} failed")
        return success_count, fail_count
        
    except Exception as e:
        logger.error(f"❌ Email retry task failed: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()


async def run_all_tasks():
    """
    Run all scheduled tasks in sequence.
    """
    logger.info("=" * 60)
    logger.info("Starting FibTool Scheduled Tasks")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("=" * 60)
    
    tasks_results = {
        "daily_deliveries": None,
        "cleanup": None,
        "email_retry": None
    }
    
    try:
        # Task 1: Create daily deliveries
        try:
            tasks_results["daily_deliveries"] = await create_daily_deliveries()
        except Exception as e:
            logger.error(f"Daily deliveries task failed: {e}")
        
        # Task 2: Cleanup old reports
        try:
            tasks_results["cleanup"] = await cleanup_old_reports(days=30)
        except Exception as e:
            logger.error(f"Cleanup task failed: {e}")
        
        # Task 3: Retry pending emails
        try:
            tasks_results["email_retry"] = await send_pending_emails()
        except Exception as e:
            logger.error(f"Email retry task failed: {e}")
        
    finally:
        logger.info("=" * 60)
        logger.info("Task Summary:")
        logger.info(f"  Daily Deliveries Created: {tasks_results['daily_deliveries']}")
        logger.info(f"  Files Cleaned: {tasks_results['cleanup']}")
        logger.info(f"  Emails Retried: {tasks_results['email_retry']}")
        logger.info("=" * 60)


if __name__ == "__main__":
    # Ensure logs directory exists
    logs_dir = backend_dir / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Run all tasks
    try:
        asyncio.run(run_all_tasks())
        logger.info("✅ All scheduled tasks completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Scheduled tasks failed: {str(e)}", exc_info=True)
        sys.exit(1)
