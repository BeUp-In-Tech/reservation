"""
Image upload endpoints for business logo and service images.
Uses Cloudinary for storage.
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from app.core.database import get_db
from app.models import AdminUser, Business, Service
from app.models.other_models import ServiceImage
from app.api.v1.admin.auth import get_current_admin
from app.services.disk_storage_service import upload_image, delete_image
router = APIRouter()


# ============== Response Models ==============

class ImageResponse(BaseModel):
    id: str | None = None
    url: str
    alt_text: str | None = None
    sort_order: int = 0


class BusinessLogoResponse(BaseModel):
    business_id: str
    logo_url: str | None


# ============== Business Logo ==============

@router.post("/{business_id}/logo", response_model=BusinessLogoResponse)
async def upload_business_logo(
    business_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Upload or replace business logo. Max 5MB, JPEG/PNG/WebP."""
    result = await db.execute(
        select(Business).where(Business.id == uuid.UUID(business_id))
    )
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    try:
        upload_result = await upload_image(
            file=file,
            folder=f"reservation/businesses/{business_id}/logo",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    business.logo_url = upload_result["url"]
    business.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(business)

    return BusinessLogoResponse(
        business_id=str(business.id),
        logo_url=business.logo_url,
    )


@router.delete("/{business_id}/logo")
async def delete_business_logo(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Remove business logo."""
    result = await db.execute(
        select(Business).where(Business.id == uuid.UUID(business_id))
    )
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    business.logo_url = None
    business.updated_at = datetime.utcnow()
    await db.commit()

    return {"message": "Logo removed"}


# ============== Service Images ==============

@router.post("/{business_id}/services/{service_id}/images", response_model=ImageResponse)
async def upload_service_image(
    business_id: str,
    service_id: str,
    file: UploadFile = File(...),
    alt_text: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Upload a service image. Max 5 per service. Max 5MB each."""
    # Validate service belongs to business
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(service_id),
            Service.business_id == uuid.UUID(business_id),
        )
    )
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Check image count limit
    result = await db.execute(
        select(ServiceImage).where(ServiceImage.service_id == uuid.UUID(service_id))
    )
    existing_images = result.scalars().all()
    if len(existing_images) >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 images per service")

    try:
        upload_result = await upload_image(
            file=file,
            folder=f"reservation/services/{service_id}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Determine sort order
    max_sort = max((img.sort_order for img in existing_images), default=-1)

    image = ServiceImage(
        business_id=uuid.UUID(business_id),
        service_id=uuid.UUID(service_id),
        image_url=upload_result["url"],
        alt_text=alt_text,
        sort_order=max_sort + 1,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    return ImageResponse(
        id=str(image.id),
        url=image.image_url,
        alt_text=image.alt_text,
        sort_order=image.sort_order,
    )


@router.get("/{business_id}/services/{service_id}/images", response_model=list[ImageResponse])
async def get_service_images(
    business_id: str,
    service_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Get all images for a service."""
    result = await db.execute(
        select(ServiceImage).where(
            ServiceImage.service_id == uuid.UUID(service_id),
            ServiceImage.business_id == uuid.UUID(business_id),
        ).order_by(ServiceImage.sort_order)
    )
    images = result.scalars().all()

    return [
        ImageResponse(
            id=str(img.id),
            url=img.image_url,
            alt_text=img.alt_text,
            sort_order=img.sort_order,
        )
        for img in images
    ]


@router.delete("/{business_id}/services/{service_id}/images/{image_id}")
async def delete_service_image(
    business_id: str,
    service_id: str,
    image_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """Delete a service image."""
    result = await db.execute(
        select(ServiceImage).where(
            ServiceImage.id == uuid.UUID(image_id),
            ServiceImage.service_id == uuid.UUID(service_id),
            ServiceImage.business_id == uuid.UUID(business_id),
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    await db.delete(image)
    await db.commit()

    return {"message": "Image deleted"}
