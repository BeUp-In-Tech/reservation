"""from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

def normalize_db_url(url: str) -> str:
    # Render sometimes provides postgres:// or postgresql://
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "postgresql+asyncpg://" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

DATABASE_URL = normalize_db_url(settings.DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "search_path": "core,public"
        }
    },
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# keep this if you want:
from sqlalchemy import text

async def debug_db_identity():
    async with AsyncSessionLocal() as session:
        row = (await session.execute(text("""
            SELECT current_database(), current_user,
                   inet_server_addr()::text, inet_server_port()::text,
                   current_setting('search_path');
        """))).first()
        print("APP DB CONNECTED TO:", row)
