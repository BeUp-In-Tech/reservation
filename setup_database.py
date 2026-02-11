"""
Database Setup Script
Run this to create all tables and seed data.

Usage:
    python setup_database.py

Or to reset database:
    python setup_database.py --reset
"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.core.database import engine, Base
from app.models import *
from app.models.other_models import *


async def setup_database(reset: bool = False):
    """Create all database tables."""
    
    async with engine.begin() as conn:
        # Create schema
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
        
        if reset:
            print("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
        
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)
        
        print("Database setup complete!")
        
        # Show table count
        result = await conn.execute(text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'core'
        """))
        count = result.scalar()
        print(f"Total tables in 'core' schema: {count}")


async def seed_admin():
    """Create default admin user."""
    from app.core.database import async_session
    from app.models.other_models import AdminUser
    from sqlalchemy import select
    import bcrypt
    
    async with async_session() as db:
        # Check if admin exists
        result = await db.execute(
            select(AdminUser).where(AdminUser.email == "admin@yourdomain.com")
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            password_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            admin = AdminUser(
                email="admin@yourdomain.com",
                password_hash=password_hash,
                full_name="System Admin",
                role="ADMIN",
                is_active=True
            )
            db.add(admin)
            await db.commit()
            print("Default admin created: admin@yourdomain.com / admin123")
        else:
            print("Admin already exists")


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    
    print("=" * 50)
    print("AI Booking System - Database Setup")
    print("=" * 50)
    
    asyncio.run(setup_database(reset))
    asyncio.run(seed_admin())
    
    print("=" * 50)
    print("Setup complete!")
    print("=" * 50)
