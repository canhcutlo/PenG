# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import QueryResponse
from app.services.queries import query_owned_documents
from app.services.auth import require_auth

router = APIRouter()


@router.get("/query", response_model=QueryResponse)
async def query_materials(
    q: str,
    top_k: int = 5,
    doc_id: str = "",
    user: dict = Depends(require_auth),
):
    """Query indexed learning materials and return a faithfulness-guarded answer."""
    if not q.strip():
        return QueryResponse(answer="", citations=[], related_chunks=[])

    try:
        return await query_owned_documents(q.strip(), top_k, doc_id, user["user_id"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")
