"""Upload endpoints: file upload and job status."""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request
from app.models.schemas import UploadResponse, JobStatusResponse
from app.db.sqlite_store import (
    insert_document,
    get_document,
    find_document_by_checksum,
    insert_job,
    get_job,
)
from app.services.file_storage import validate_upload, save_upload, compute_checksum
from app.services.processing import process_document_sync
from app.services.auth import require_auth, verify_csrf
from app.config import settings
from typing import Annotated

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    category: Annotated[str, Form()] = "image",
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Upload a learning material file. Creates a document and processing job."""

    if category not in ("audio", "image", "pdf", "video"):
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    validate_upload(file, category)

    doc_id = uuid.uuid4().hex[:12]
    job_id = uuid.uuid4().hex[:12]
    original_name = file.filename or "upload"

    file_path = save_upload(file, doc_id)
    checksum = compute_checksum(file_path)
    file_size = file_path.stat().st_size

    existing = find_document_by_checksum(checksum, user["user_id"])
    if existing:
        dup_job_id = uuid.uuid4().hex[:12]
        insert_job(dup_job_id, existing["doc_id"], "extract", user["user_id"])
        if settings.process_on_upload:
            background_tasks.add_task(
                process_document_sync, existing["doc_id"], dup_job_id, user["user_id"]
            )
        return UploadResponse(
            doc_id=existing["doc_id"],
            job_id=dup_job_id,
            filename=existing["filename"],
            category=existing["category"],
            status=existing.get("status", "completed"),
        )

    doc = insert_document(doc_id, file_path.name, original_name, category, file_size, checksum, user["user_id"])
    job = insert_job(job_id, doc_id, "extract", user["user_id"])

    if settings.process_on_upload:
        background_tasks.add_task(process_document_sync, doc_id, job_id, user["user_id"])

    return UploadResponse(
        doc_id=doc["doc_id"],
        job_id=job["job_id"],
        filename=doc["filename"],
        category=doc["category"],
        status=doc["status"],
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, user: dict = Depends(require_auth)):
    """Get processing job status."""
    job = get_job(job_id, user["user_id"])
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job["job_id"],
        doc_id=job["doc_id"],
        status=job["status"],
        progress=job["progress"],
        error_message=job["error_message"],
    )
