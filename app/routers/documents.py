# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Document listing, source, and artifact endpoints."""
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from app.models.schemas import Artifact, DocumentSourceResponse, SourceChunk
from app.db.sqlite_store import get_document, get_documents_for_user
from app.db.artifact_store import get_artifacts_by_doc, get_latest_artifact
from app.db.chunk_store import (
    count_source_chunks,
    get_source_chunk,
    get_source_chunk_by_locator,
    list_source_chunks,
)
from app.services.artifacts import regenerate_artifact
from app.services.auth import require_auth, verify_csrf
from app.services.file_storage import get_document_file_path

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.get("/documents")
async def list_documents(limit: int = 100, offset: int = 0, user: dict = Depends(require_auth)):
    """List documents owned by the current user."""
    rows = get_documents_for_user(user["user_id"], limit, offset)
    return [
        {
            "doc_id": r["doc_id"],
            "filename": r["filename"],
            "original_name": r["original_name"],
            "category": r["category"],
            "file_size": r["file_size"],
            "status": r["status"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def _source_chunk_response(row: dict) -> SourceChunk:
    return SourceChunk(
        chunk_id=row["chunk_id"],
        doc_id=row["doc_id"],
        position=row["position"],
        text=row["text"],
        page=row.get("page"),
        scene=row.get("scene"),
        timestamp=row.get("timestamp"),
        metadata=row.get("metadata") or {},
    )


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
    if not get_document(doc_id, user["user_id"]):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    located = get_source_chunk_by_locator(
        doc_id,
        user["user_id"],
        chunk_id=chunk_id,
        page=page,
        scene=scene,
        timestamp=timestamp,
    )
    if located:
        offset = max(0, located["position"] - (located["position"] % limit))
    rows = list_source_chunks(doc_id, user["user_id"], limit, offset)
    return DocumentSourceResponse(
        doc_id=doc_id,
        total=count_source_chunks(doc_id, user["user_id"]),
        limit=limit,
        offset=offset,
        chunks=[_source_chunk_response(row) for row in rows],
    )


@router.get("/documents/{doc_id}/source/chunks/{chunk_id}", response_model=SourceChunk)
@router.get("/documents/{doc_id}/source/{chunk_id}", response_model=SourceChunk)
async def get_document_source_chunk(
    doc_id: str,
    chunk_id: str,
    user: dict = Depends(require_auth),
):
    """Get an exact source chunk from an owned document."""
    if not get_document(doc_id, user["user_id"]):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    chunk = get_source_chunk(doc_id, chunk_id, user["user_id"])
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")
    return _source_chunk_response(chunk)


@router.get("/documents/{doc_id}/original")
@router.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: str, user: dict = Depends(require_auth)):
    """Return the original content for an owned document inline."""
    doc = get_document(doc_id, user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    try:
        file_path = get_document_file_path(doc_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Original content not found")
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
    doc = get_document(doc_id, user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    rows = get_artifacts_by_doc(doc_id, artifact_type)
    return [_artifact_response(r) for r in rows]


@router.get("/documents/{doc_id}/summary")
async def get_summary(doc_id: str, user: dict = Depends(require_auth)):
    """Get the latest completed summary artifact for a document."""
    doc = get_document(doc_id, user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    artifact = get_latest_artifact(doc_id, "summary", status="completed")
    if not artifact:
        raise HTTPException(status_code=404, detail="No completed summary found")

    return _artifact_response(artifact)


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

    doc = get_document(doc_id, user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    artifact = await regenerate_artifact(doc_id, user["user_id"], artifact_type)
    return _artifact_response(artifact)


def _artifact_response(row: dict) -> dict:
    return Artifact(**row).model_dump()
