# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""File storage: validation, checksum, save, cleanup."""
import hashlib
import shutil
import os
from pathlib import Path
import aiofiles
from fastapi import UploadFile, HTTPException
from app.config import settings

UPLOAD_CHUNK_SIZE = 1024 * 1024

EXTENSION_MAP = {
    "audio": {".mp3", ".wav", ".m4a", ".ogg", ".flac"},
    "image": {".png", ".jpg", ".jpeg", ".bmp", ".tiff"},
    "pdf": {".pdf", ".txt", ".md", ".docx"},
    "video": {".mp4", ".avi", ".mov", ".mkv", ".webm"},
}

MIME_MAP = {
    "audio": {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/m4a", "audio/ogg", "audio/flac"},
    "image": {"image/png", "image/jpeg", "image/bmp", "image/tiff"},
    "pdf": {
        "application/pdf",
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    "video": {
        "video/mp4",
        "video/x-msvideo",
        "video/quicktime",
        "video/x-matroska",
        "video/webm",
    },
}


def _safe_filename(name: str) -> str:
    """Remove path separators and dangerous characters from filename."""
    return "".join(c for c in name if c.isalnum() or c in "._- ").strip()[:128]


def validate_upload(file: UploadFile, category: str):
    """Validate file extension, MIME type, and size. Raises HTTPException on failure."""
    if category not in EXTENSION_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in EXTENSION_MAP[category]:
        allowed = ", ".join(EXTENSION_MAP[category])
        raise HTTPException(
            status_code=400,
            detail=f"Invalid extension '{ext}' for category '{category}'. Allowed: {allowed}",
        )

    if file.content_type and file.content_type.strip():
        if file.content_type not in MIME_MAP[category]:
            allowed = ", ".join(MIME_MAP[category])
            raise HTTPException(
                status_code=400,
                detail=f"Invalid MIME type '{file.content_type}' for category '{category}'. Allowed: {allowed}",
            )


def validate_size(file_size: int):
    """Check file size against limit. Raises HTTPException on failure."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size} bytes). Max: {settings.max_upload_size_mb}MB",
        )


def get_doc_dir(doc_id: str) -> Path:
    """Get the storage directory for a document."""
    return settings.upload_dir / doc_id


async def save_upload(file: UploadFile, doc_id: str) -> tuple[Path, int, str]:
    """Stream an upload to disk and return path, byte size, and SHA-256.

    The size limit is enforced while streaming so an oversized upload is never
    held entirely in memory or left behind as a partial file.
    """
    doc_dir = get_doc_dir(doc_id)
    doc_dir.mkdir(parents=True, exist_ok=True)

    safe_name = _safe_filename(file.filename or "upload") or "upload"
    file_path = doc_dir / safe_name
    partial_path = doc_dir / f".{safe_name}.part"
    checksum = hashlib.sha256()
    file_size = 0

    try:
        async with aiofiles.open(partial_path, "wb") as output:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                file_size += len(chunk)
                validate_size(file_size)
                checksum.update(chunk)
                await output.write(chunk)
        os.replace(partial_path, file_path)
    except Exception:
        partial_path.unlink(missing_ok=True)
        if doc_dir.exists() and not any(doc_dir.iterdir()):
            doc_dir.rmdir()
        raise

    return file_path, file_size, checksum.hexdigest()


def cleanup_document(doc_id: str):
    """Remove document directory and all its contents."""
    doc_dir = get_doc_dir(doc_id)
    if doc_dir.exists():
        shutil.rmtree(doc_dir)


def get_document_file_path(doc_id: str) -> Path:
    """Get the path to the document's first file."""
    doc_dir = get_doc_dir(doc_id)
    files = list(doc_dir.glob("*"))
    if not files:
        raise FileNotFoundError(f"No file found for document {doc_id}")
    return files[0]
