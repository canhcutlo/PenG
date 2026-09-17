# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, HTTPException, Depends, Request
from app.services.auth import require_auth, verify_csrf
from app.services.history import add_history, list_history

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.get("/history")
async def get_learning_history(limit: int = 20, user: dict = Depends(require_auth)):
    """Get recent learning activities from SQLite."""
    return list_history(user["user_id"], limit)


@router.post("/history")
async def log_learning_activity(
    request: Request,
    doc_id: str,
    action: str,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Log a learning activity."""
    allowed = ("uploaded", "viewed", "quizzed", "mindmapped",
               "summary_generated", "mindmap_generated", "artifact_failed")
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    if not add_history(doc_id, action, user["user_id"]):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return {"status": "ok", "doc_id": doc_id, "action": action}
