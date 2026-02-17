from app.models import Service
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid


async def load_business_services(db: AsyncSession, business_id: uuid.UUID) -> dict:
    """Fetch services for a given business."""
    
    result = await db.execute(
        select(Service)
        .where(Service.business_id == business_id, Service.is_active == True)
    )
    
    services = result.scalars().all()
    
    services_list = [
        {
            "id": str(s.id),
            "service_name": s.service_name,
            "description": s.description,
            "base_price": float(s.base_price) if s.base_price else None,
            "currency": s.currency,
            "duration_minutes": s.duration_minutes,
        }
        for s in services
    ]
    
    return {
        "available_services": services_list,
    }