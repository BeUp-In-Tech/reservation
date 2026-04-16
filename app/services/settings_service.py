"""
Platform settings service.
Stores/retrieves platform-wide config (API keys, etc.) from the DB.
Falls back to .env if not set in DB.
"""

import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.platform_settings import PlatformSettings


# Keys we treat as sensitive (will be masked in GET responses)
SENSITIVE_KEYS = {"openai_api_key"}

# Keys that fall back to env vars if not set in DB
ENV_FALLBACKS = {
    "openai_api_key": "OPENAI_API_KEY",
}


async def get_setting(db: AsyncSession, key: str) -> str | None:
    """Read a setting from DB. Falls back to env var if not found."""
    result = await db.execute(
        select(PlatformSettings).where(PlatformSettings.key == key)
    )
    row = result.scalar_one_or_none()
    if row and row.value:
        return row.value

    # Fall back to environment variable
    env_key = ENV_FALLBACKS.get(key)
    if env_key:
        return os.getenv(env_key)
    return None


async def set_setting(db: AsyncSession, key: str, value: str) -> None:
    """Create or update a setting in the DB."""
    result = await db.execute(
        select(PlatformSettings).where(PlatformSettings.key == key)
    )
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(PlatformSettings(key=key, value=value))
    await db.commit()


def mask_value(value: str) -> str:
    """Mask a sensitive value — show first 10 and last 4 characters."""
    if not value:
        return ""
    if len(value) <= 14:
        return "***"
    return f"{value[:10]}...{value[-4:]}"