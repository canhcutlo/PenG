# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Upload and processing-job orchestration."""
import uuid

from fastapi import UploadFile

from app.config import settings
from app.db.sqlite_store import (
    find_document_by_checksum,
    get_job,
    insert_document,
    insert_job,
)
from app.models.schemas import JobStatusResponse, UploadResponse
from app.services.file_storage import (
    cleanup_document,
    save_upload,
    validate_upload,
)


async def create_upload(
    file: UploadFile,
    category: str,
    user_id: str,
) -> tuple[UploadResponse, tuple[str, str, str] | None]:
    validate_upload(file, category)
    doc_id = uuid.uuid4().hex[:12]
    original_name = file.filename or "upload"
    file_path, file_size, checksum = await save_upload(file, doc_id)

    existing = find_document_by_checksum(checksum, user_id)
    if existing:
        cleanup_document(doc_id)
        job_id = uuid.uuid4().hex[:12]
        insert_job(job_id, existing["doc_id"], "extract", user_id)
        response = UploadResponse(
            doc_id=existing["doc_id"],
            job_id=job_id,
            filename=existing["filename"],
            original_name=existing.get("original_name") or existing["filename"],
            category=existing["category"],
            status=existing.get("status", "completed"),
        )
        task = (existing["doc_id"], job_id, user_id)
        return response, task if settings.process_on_upload else None

    job_id = uuid.uuid4().hex[:12]
    doc = insert_document(
        doc_id,
        file_path.name,
        original_name,
        category,
        file_size,
        checksum,
        user_id,
    )
    job = insert_job(job_id, doc_id, "extract", user_id)
    response = UploadResponse(
        doc_id=doc["doc_id"],
        job_id=job["job_id"],
        filename=doc["filename"],
        original_name=doc.get("original_name") or doc["filename"],
        category=doc["category"],
        status=doc["status"],
    )
    task = (doc_id, job_id, user_id)
    return response, task if settings.process_on_upload else None


def get_owned_job(job_id: str, user_id: str) -> JobStatusResponse | None:
    job = get_job(job_id, user_id)
    if not job:
        return None
    return JobStatusResponse(
        job_id=job["job_id"],
        doc_id=job["doc_id"],
        status=job["status"],
        progress=job["progress"],
        stage=job.get("stage"),
        stage_label=job.get("stage_label"),
        error_message=job["error_message"],
    )
