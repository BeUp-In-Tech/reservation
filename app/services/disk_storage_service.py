"""
Disk storage helper.
Saves uploaded images to a local/mounted directory and returns public URLs.
Used in place of Cloudinary.
"""

import os
import uuid
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings


# File type and size validation
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _get_upload_root() -> Path:
    """Get the base upload directory, creating it if needed."""
    root = Path(settings.UPLOAD_DIR).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


async def upload_image(
    file: UploadFile,
    folder: str = "general",
    max_size_mb: int = 5,
) -> dict:
    """
    Save an uploaded image to the disk.

    Args:
        file: FastAPI UploadFile
        folder: Sub-folder inside UPLOAD_DIR (e.g. "businesses/{id}/logo")
        max_size_mb: Max file size in MB

    Returns:
        {"url": "https://host/uploads/xxx", "public_id": "folder/file.jpg", "path": "/abs/path"}
    """
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise ValueError(
            f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, WebP, GIF"
        )

    # Read and check size
    content = await file.read()
    if len(content) > max_size_mb * 1024 * 1024:
        raise ValueError(f"File too large. Maximum size: {max_size_mb}MB")

    # Build target path
    upload_root = _get_upload_root()
    target_folder = upload_root / folder
    target_folder.mkdir(parents=True, exist_ok=True)

    ext = EXTENSION_MAP.get(file.content_type, ".jpg")
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = target_folder / filename

    # Write file
    with open(file_path, "wb") as f:
        f.write(content)

    # Build public URL
    # relative_path uses forward slashes so it works in URLs
    relative_path = f"{folder}/{filename}".replace("\\", "/")
    base_url = settings.PUBLIC_BASE_URL.rstrip("/") or ""
    public_url = f"{base_url}/uploads/{relative_path}"

    return {
        "url": public_url,
        "public_id": relative_path,
        "path": str(file_path),
    }


def delete_image(public_id: str) -> bool:
    """
    Delete an image from disk by its public_id (relative path).

    public_id example: "businesses/abc123/logo/xyz.jpg"
    """
    try:
        upload_root = _get_upload_root()
        file_path = upload_root / public_id

        # Safety check: ensure path is inside the upload root
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(upload_root)):
            return False

        if resolved.exists():
            resolved.unlink()
            return True
        return False
    except Exception:
        return False


def is_disk_url(url: str) -> bool:
    """Check if a URL points to our disk storage (vs Cloudinary)."""
    if not url:
        return False
    return "/uploads/" in url