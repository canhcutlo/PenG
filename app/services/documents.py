# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Owned document, source, and artifact access."""
from pathlib import Path

from app.db.artifact_store import get_artifacts_by_doc, get_latest_artifact
from app.db.chunk_store import (
    count_source_chunks,
    get_source_chunk,
    get_source_chunk_by_locator,
    list_source_chunks,
)
from app.db.sqlite_store import get_document, get_documents_for_user
from app.models.schemas import Artifact, DocumentSourceResponse, SourceChunk
from app.services.artifacts import regenerate_artifact
from app.services.file_storage import get_document_file_path


def list_owned_documents(user_id: str, limit: int, offset: int) -> list[dict]:
    return [
        {key: row[key] for key in (
            "doc_id", "filename", "original_name", "category", "file_size",
            "status", "created_at", "updated_at",
        )}
        for row in get_documents_for_user(user_id, limit, offset)
    ]


def get_owned_document(doc_id: str, user_id: str) -> dict | None:
    return get_document(doc_id, user_id)


def get_owned_document_file(doc_id: str, user_id: str) -> tuple[dict, Path] | None:
    doc = get_document(doc_id, user_id)
    if not doc:
        return None
    return doc, get_document_file_path(doc_id)


def list_owned_source(
    doc_id: str,
    user_id: str,
    limit: int,
    offset: int,
    **locator,
) -> DocumentSourceResponse | None:
    if not get_document(doc_id, user_id):
        return None
    located = get_source_chunk_by_locator(doc_id, user_id, **locator)
    if located:
        offset = max(0, located["position"] - (located["position"] % limit))
    rows = list_source_chunks(doc_id, user_id, limit, offset)
    return DocumentSourceResponse(
        doc_id=doc_id,
        total=count_source_chunks(doc_id, user_id),
        limit=limit,
        offset=offset,
        chunks=[source_chunk_response(row) for row in rows],
    )


def get_owned_source_chunk(doc_id: str, chunk_id: str, user_id: str) -> SourceChunk | None:
    if not get_document(doc_id, user_id):
        raise LookupError(f"Document {doc_id} not found")
    row = get_source_chunk(doc_id, chunk_id, user_id)
    return source_chunk_response(row) if row else None


def list_owned_artifacts(doc_id: str, user_id: str, artifact_type: str | None = None) -> list[dict] | None:
    if not get_document(doc_id, user_id):
        return None
    return [Artifact(**row).model_dump() for row in get_artifacts_by_doc(doc_id, artifact_type)]


def get_owned_summary(doc_id: str, user_id: str) -> dict | None:
    if not get_document(doc_id, user_id):
        raise LookupError(f"Document {doc_id} not found")
    artifact = get_latest_artifact(doc_id, "summary", status="completed")
    return Artifact(**artifact).model_dump() if artifact else None


async def regenerate_owned_artifact(doc_id: str, user_id: str, artifact_type: str) -> dict:
    if not get_document(doc_id, user_id):
        raise LookupError(f"Document {doc_id} not found")
    row = await regenerate_artifact(doc_id, user_id, artifact_type)
    return Artifact(**row).model_dump()


def source_chunk_response(row: dict) -> SourceChunk:
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
