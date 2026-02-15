#!/usr/bin/env bash
set -e

echo "=== Running database migrations ==="
alembic upgrade head

echo "=== Initializing admin user ==="
python -c "
import asyncio
from app.api.v1.admin.auth import ensure_admin_exists
from app.core.database import AsyncSessionLocal

async def init():
    async with AsyncSessionLocal() as db:
        await ensure_admin_exists(db)
        print('Admin user ready')

asyncio.run(init())
"

echo "=== Starting API server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}