"""Save uploaded files to disk (Upload stage: "Save File in Server (uploads/)")."""
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings
from app.services.ocr.pipeline import SUPPORTED_TYPES


class StorageError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


async def save_upload(file: UploadFile) -> tuple[str, Path, int]:
    """Returns (stored_filename, absolute_path, size_bytes)."""
    settings = get_settings()
    content_type = (file.content_type or "").lower()
    if content_type not in SUPPORTED_TYPES:
        raise StorageError(f"Unsupported file type '{content_type}'. Upload a PDF or image.", 415)

    ext = Path(file.filename or "").suffix.lower() or _default_ext(content_type)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / stored_name

    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise StorageError(f"File exceeds the {settings.max_upload_mb} MB limit.", 413)
            out.write(chunk)
    if size == 0:
        dest.unlink(missing_ok=True)
        raise StorageError("Uploaded file is empty.", 400)
    return stored_name, dest, size


def _default_ext(content_type: str) -> str:
    return {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
            "image/webp": ".webp", "image/tiff": ".tiff", "image/bmp": ".bmp"}.get(content_type, "")


def delete_stored(stored_name: str) -> None:
    (Path(get_settings().upload_dir) / stored_name).unlink(missing_ok=True)
