# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Document listing, source, and artifact endpoints."""
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from app.models.schemas import DocumentSourceResponse, SourceChunk
from app.services.auth import require_auth, verify_csrf
from app.services.documents import (
    get_owned_document_file,
    get_owned_source_chunk,
    get_owned_summary,
    list_owned_artifacts,
    list_owned_documents,
    list_owned_source,
    regenerate_owned_artifact,
)

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.get("/documents")
async def list_documents(limit: int = 100, offset: int = 0, user: dict = Depends(require_auth)):
    """List documents owned by the current user."""
    return list_owned_documents(user["user_id"], limit, offset)


@router.get("/documents/{doc_id}/source", response_model=DocumentSourceResponse)
async def list_document_source(
    doc_id: str,
    limit: int = 100,
    offset: int = 0,
    chunk_id: str | None = None,
    page: int | None = None,
    scene: int | None = None,
    timestamp: float | None = None,
    user: dict = Depends(require_auth),
):
    """List source chunks for an owned document."""
    if limit < 1 or limit > 500 or offset < 0:
        raise HTTPException(status_code=422, detail="limit must be 1..500 and offset must be non-negative")
    result = list_owned_source(
        doc_id,
        user["user_id"],
        limit,
        offset,
        chunk_id=chunk_id,
        page=page,
        scene=scene,
        timestamp=timestamp,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return result


@router.get("/documents/{doc_id}/source/chunks/{chunk_id}", response_model=SourceChunk)
@router.get("/documents/{doc_id}/source/{chunk_id}", response_model=SourceChunk)
async def get_document_source_chunk(
    doc_id: str,
    chunk_id: str,
    user: dict = Depends(require_auth),
):
    """Get an exact source chunk from an owned document."""
    try:
        chunk = get_owned_source_chunk(doc_id, chunk_id, user["user_id"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")
    return chunk


@router.get("/documents/{doc_id}/original")
@router.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: str, user: dict = Depends(require_auth)):
    """Return the original content for an owned document inline."""
    try:
        owned = get_owned_document_file(doc_id, user["user_id"])
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Original content not found")
    if not owned:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    doc, file_path = owned
    media_type = mimetypes.guess_type(doc["original_name"])[0] or "application/octet-stream"
    safe_name = doc["original_name"].replace('"', "")
    disposition = f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{quote(doc['original_name'])}"
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/documents/{doc_id}/artifacts")
async def list_artifacts(
    doc_id: str,
    artifact_type: str | None = None,
    user: dict = Depends(require_auth),
):
    """List artifacts for a document."""
    rows = list_owned_artifacts(doc_id, user["user_id"], artifact_type)
    if rows is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return rows


@router.get("/documents/{doc_id}/summary")
async def get_summary(doc_id: str, user: dict = Depends(require_auth)):
    """Get the latest completed summary artifact for a document."""
    try:
        artifact = get_owned_summary(doc_id, user["user_id"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not artifact:
        raise HTTPException(status_code=404, detail="No completed summary found")

    return artifact


@router.post("/documents/{doc_id}/artifacts/regenerate")
async def regenerate_artifact_endpoint(
    request: Request,
    doc_id: str,
    artifact_type: str,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Regenerate a summary or mindmap artifact."""
    if artifact_type not in ("summary", "mindmap"):
        raise HTTPException(status_code=400, detail="artifact_type must be summary or mindmap")

    try:
        return await regenerate_owned_artifact(doc_id, user["user_id"], artifact_type)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
