from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime, time

import uuid

from app.core.database import get_db
from app.models import Service, AdminUser

from app.api.v1.admin.auth import get_current_admin


router = APIRouter()






# ============== Service Models ==============

class ServiceCreate(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=200)
    slug: str
    description: str | None = None
    timezone: str = Field(..., min_length=1, max_length=64)
    open_time: str | None = "09:00"
    close_time: str | None = "18:00"

class ServiceUpdate(BaseModel):

    service_name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    timezone: str | None = None
    open_time: str | None = None
    close_time: str | None = None


class ServiceResponse(BaseModel):
    id: str
    business_id: str
    slug: str
    service_name: str
    description: str | None
    is_active: bool
    timezone: str
    open_time: str | None
    close_time: str | None


# ============== Helpers ==============

def parse_time(time_str: str | None) -> time | None:
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except:
        return None


def format_time(t: time | None) -> str | None:
    if not t:
        return None
    return t.strftime("%H:%M")


def service_to_response(service: Service) -> ServiceResponse:
    return ServiceResponse(
        id=str(service.id),
        business_id=str(service.business_id),
        slug=service.slug,
        service_name=service.service_name,
        description=service.description,
        is_active=service.is_active,
        timezone=service.timezone,
        open_time=format_time(service.open_time),
        close_time=format_time(service.close_time),
    )



# ============== Service Endpoints ==============

@router.get("/businesses/{bid}/services", response_model=list[ServiceResponse])
async def list_services(
    bid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """List all services for a business with operating hours."""
    result = await db.execute(
        select(Service)
        .where(Service.business_id == uuid.UUID(bid))
        .order_by(Service.is_popular.desc(), Service.created_at.desc())
    )
    services = result.scalars().all()
    return [service_to_response(s) for s in services]


@router.post("/businesses/{bid}/services", response_model=ServiceResponse)
async def create_service(
    bid: str,
    request: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new service with operating hours."""
    service_name = request.service_name
    
    service = Service(
        business_id=uuid.UUID(bid),
        slug=request.slug,
        service_name=request.service_name,
        description=request.description or "",
        base_price=None,
        currency="BDT",
        duration_minutes=60,
        is_active=True,
        open_time=parse_time(request.open_time),
        close_time=parse_time(request.close_time),
        category="GENERAL",
        is_popular=False,
        max_capacity=1,
        timezone=request.timezone,
        created_at=datetime.utcnow(),
    )

    db.add(service)
    await db.commit()
    await db.refresh(service)

    return service_to_response(service)


@router.get("/businesses/{bid}/services/{sid}", response_model=ServiceResponse)
async def get_service(
    bid: str,
    sid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(sid),
            Service.business_id == uuid.UUID(bid)
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service_to_response(service)


@router.patch("/businesses/{bid}/services/{sid}", response_model=ServiceResponse)
async def update_service(
    bid: str,
    sid: str,
    request: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(sid),
            Service.business_id == uuid.UUID(bid)
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if request.service_name is not None:
        service.service_name = request.service_name
    if request.description is not None:
        service.description = request.description

    if request.is_active is not None:
        service.is_active = request.is_active
    if request.timezone is not None:
        service.timezone = request.timezone
    if request.open_time is not None:
        service.open_time = parse_time(request.open_time)
    if request.close_time is not None:
        service.close_time = parse_time(request.close_time)
    

    service.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(service)

    return service_to_response(service)


@router.delete("/businesses/{bid}/services/{sid}")
async def delete_service(
    bid: str,
    sid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    try:
        service_uuid = uuid.UUID(sid.strip())
        business_uuid = uuid.UUID(bid.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    result = await db.execute(
        select(Service).where(
            Service.id == service_uuid,
            Service.business_id == business_uuid
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    await db.delete(service)
    await db.commit()

    return {"message": "Service deleted permanently"}