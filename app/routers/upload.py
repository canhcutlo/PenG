# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Upload endpoints: file upload and job status."""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request
from app.models.schemas import UploadResponse, JobStatusResponse
from app.services.processing import process_document_sync
from app.services.auth import require_auth, verify_csrf
from app.services.uploads import create_upload, get_owned_job
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

    response, task = create_upload(file, category, user["user_id"])
    if task:
        # ponytail: BackgroundTasks is single-process and non-durable; move processing to a durable queue before multi-host deployment.
        background_tasks.add_task(process_document_sync, *task)
    return response


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, user: dict = Depends(require_auth)):
    """Get processing job status."""
    job = get_owned_job(job_id, user["user_id"])
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job
