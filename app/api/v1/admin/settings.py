"""
Admin Settings Endpoints
========================
GET   /api/v1/admin/settings/api-keys  - View current API keys (masked)
PATCH /api/v1/admin/settings/api-keys  - Update API keys
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.admin.auth import get_current_admin
from app.services.settings_service import (
    get_setting, set_setting, mask_value, SENSITIVE_KEYS
)

router = APIRouter(
    prefix="/api/v1/admin/settings",
    tags=["Admin - Settings"],
)


class ApiKeysOut(BaseModel):
    openai_api_key: str  # masked


class ApiKeysUpdate(BaseModel):
    openai_api_key: str | None = None


@router.get("/api-keys", response_model=ApiKeysOut)
async def get_api_keys(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """View current API keys (values are masked for security)."""
    openai_key = await get_setting(db, "openai_api_key") or ""
    return ApiKeysOut(openai_api_key=mask_value(openai_key))


@router.patch("/api-keys", response_model=ApiKeysOut)
async def update_api_keys(
    payload: ApiKeysUpdate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """Update API keys. Only non-null fields are updated."""
    if payload.openai_api_key is not None and payload.openai_api_key.strip():
        key = payload.openai_api_key.strip()
        if not key.startswith("sk-"):
            raise HTTPException(
                status_code=400,
                detail="Invalid OpenAI key format (must start with 'sk-')"
            )
        await set_setting(db, "openai_api_key", key)

    openai_key = await get_setting(db, "openai_api_key") or ""
    return ApiKeysOut(openai_api_key=mask_value(openai_key))