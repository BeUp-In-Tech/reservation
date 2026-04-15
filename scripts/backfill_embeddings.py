"""
One-time script to backfill embeddings for all existing businesses and services.
Run with: python -m scripts.backfill_embeddings
"""
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.business import Business
from app.models.service import Service
from app.services.embedding_service import sync_business_embeddings, sync_service_embeddings


async def main():
    async with AsyncSessionLocal() as db:
        # Backfill businesses
        print("Backfilling businesses...")
        result = await db.execute(select(Business))
        businesses = result.scalars().all()
        for biz in businesses:
            try:
                count = await sync_business_embeddings(db, biz)
                print(f"  ✓ {biz.business_name}: {count} chunks")
            except Exception as e:
                print(f"  ✗ {biz.business_name}: {e}")

        # Backfill services
        print("\nBackfilling services...")
        result = await db.execute(select(Service))
        services = result.scalars().all()
        for svc in services:
            try:
                count = await sync_service_embeddings(db, svc)
                print(f"  ✓ {svc.service_name}: {count} chunks")
            except Exception as e:
                print(f"  ✗ {svc.service_name}: {e}")

        print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())