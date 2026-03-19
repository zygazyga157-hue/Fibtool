"""
Database initialization script to create tables and seed initial data.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import engine, SessionLocal, Base
from app.models import Plan, PlanType, PlanInterval, User
from app.core.security import hash_password


def init_database():
    """Initialize database with tables."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created")


def seed_plans():
    """Seed initial plans."""
    db = SessionLocal()
    
    try:
        # Check if plans already exist
        existing_plans = db.query(Plan).count()
        if existing_plans > 0:
            print(f"✓ Plans already exist ({existing_plans} plans)")
            return
        
        plans = [
            Plan(
                name="Single Report",
                type=PlanType.ONE_OFF,
                price=500,  # $5.00
                currency="USD",
                description="One-time Fibtool analysis report for a single symbol"
            ),
            Plan(
                name="Monthly Subscription",
                type=PlanType.SUBSCRIPTION,
                price=2000,  # $20.00
                currency="USD",
                interval=PlanInterval.MONTHLY,
                description="Monthly subscription with daily reports"
            ),
            Plan(
                name="Yearly Subscription",
                type=PlanType.SUBSCRIPTION,
                price=20000,  # $200.00
                currency="USD",
                interval=PlanInterval.YEARLY,
                description="Annual subscription with daily reports (2 months free)"
            ),
        ]
        
        for plan in plans:
            db.add(plan)
        
        db.commit()
        print(f"✓ Seeded {len(plans)} plans")
        
    finally:
        db.close()


def create_admin_user():
    """Create a default admin user."""
    db = SessionLocal()
    
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.email == "admin@fibtool.com").first()
        if admin:
            print("✓ Admin user already exists")
            return
        
        admin = User(
            email="admin@fibtool.com",
            password_hash=hash_password("admin123"),
            name="Admin User",
            is_active=True,
            is_admin=True
        )
        
        db.add(admin)
        db.commit()
        print("✓ Created admin user (admin@fibtool.com / admin123)")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("\n=== Database Initialization ===\n")
    init_database()
    seed_plans()
    create_admin_user()
    print("\n✓ Database initialization complete!\n")
