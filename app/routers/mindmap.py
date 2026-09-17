# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.artifacts import get_or_generate_mindmap
from app.services.auth import require_auth

router = APIRouter()


class MindmapResponse(BaseModel):
    doc_id: str
    markdown: str
    source: str = "generated"


@router.get("/mindmap/{doc_id}", response_model=MindmapResponse)
async def get_mindmap(doc_id: str, user: dict = Depends(require_auth)):
    """Return a sanitized markdown mindmap for a document. Prefer stored artifact."""
    try:
        result = await get_or_generate_mindmap(doc_id, user["user_id"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mindmap generation failed: {exc}")
    if not result:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    markdown, source = result
    return MindmapResponse(doc_id=doc_id, markdown=markdown, source=source)
