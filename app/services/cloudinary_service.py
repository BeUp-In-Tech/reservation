"""
Cloudinary upload helper.
Handles image uploads for business logos and service images.
"""

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
from app.core.config import settings


def _configure():
    """Configure cloudinary from settings. Called once per upload."""
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


async def upload_image(
    file: UploadFile,
    folder: str = "reservation",
    max_size_mb: int = 5,
) -> dict:
    """
    Upload an image to Cloudinary.

    Args:
        file: FastAPI UploadFile
        folder: Cloudinary folder name
        max_size_mb: Max file size in MB

    Returns:
        {"url": "https://...", "public_id": "reservation/abc123"}
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise ValueError(f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, WebP, GIF")

    # Read and check size
    content = await file.read()
    if len(content) > max_size_mb * 1024 * 1024:
        raise ValueError(f"File too large. Maximum size: {max_size_mb}MB")

    _configure()

    # Upload to Cloudinary
    result = cloudinary.uploader.upload(
        content,
        folder=folder,
        resource_type="image",
        transformation=[
            {"width": 1200, "height": 1200, "crop": "limit"},
            {"quality": "auto", "fetch_format": "auto"},
        ],
    )

    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
    }


def delete_image(public_id: str) -> bool:
    """Delete an image from Cloudinary by public_id."""
    try:
        _configure()
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception:
        return False
