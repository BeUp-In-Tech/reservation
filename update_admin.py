# update_admin.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:123456@localhost:5432/reservation_dev"

async def update_admin_email():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await session.execute(
            text("UPDATE core.admin_users SET email = 'beupintech@gmail.com' WHERE email = 'mondal15-5329@diu.edu.bd'")
        )
        await session.commit()
        print("✅ Admin email updated to beupintech@gmail.com")

asyncio.run(update_admin_email())