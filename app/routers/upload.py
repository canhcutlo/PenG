"""Upload endpoints: file upload and job status."""
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from app.models.schemas import UploadResponse, JobStatusResponse
from app.db.sqlite_store import (
    insert_document,
    get_document,
    find_document_by_checksum,
    insert_job,
    get_job,
)
from app.services.file_storage import validate_upload, save_upload, compute_checksum
from app.services.processing import process_document
from app.config import settings
from typing import Annotated

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    category: Annotated[str, Form()] = "image",
):
    """Upload a learning material file. Creates a document and processing job."""

    # Validate
    if category not in ("audio", "image", "pdf", "video"):
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    validate_upload(file, category)

    doc_id = uuid.uuid4().hex[:12]
    job_id = uuid.uuid4().hex[:12]
    original_name = file.filename or "upload"

    # Save file
    file_path = save_upload(file, doc_id)
    checksum = compute_checksum(file_path)
    file_size = file_path.stat().st_size

    # Check for duplicate
    existing = find_document_by_checksum(checksum)
    if existing:
        # Duplicate content found — create a new job for re-indexing
        dup_job_id = uuid.uuid4().hex[:12]
        insert_job(dup_job_id, existing["doc_id"], "extract")
        return UploadResponse(
            doc_id=existing["doc_id"],
            job_id=dup_job_id,
            filename=existing["filename"],
            category=existing["category"],
            status=existing.get("status", "completed"),
        )

    # Create records
    doc = insert_document(doc_id, file_path.name, original_name, category, file_size, checksum)
    job = insert_job(job_id, doc_id, "extract")

    # Start background processing unless disabled
    if settings.process_on_upload:
        background_tasks.add_task(process_document, doc_id, job_id)

    return UploadResponse(
        doc_id=doc["doc_id"],
        job_id=job["job_id"],
        filename=doc["filename"],
        category=doc["category"],
        status=doc["status"],
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get processing job status."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job["job_id"],
        doc_id=job["doc_id"],
        status=job["status"],
        progress=job["progress"],
        error_message=job["error_message"],
    )
