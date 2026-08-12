from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import LearningActivity
from app.db.sqlite_store import get_activities, log_activity as db_log_activity
from app.services.auth import require_auth, verify_csrf

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.get("/history")
async def get_learning_history(limit: int = 20, user: dict = Depends(require_auth)):
    """Get recent learning activities from SQLite."""
    from app.db.sqlite_store import get_documents_for_user

    rows = get_activities(user["user_id"], limit)
    docs = {d["doc_id"]: d for d in get_documents_for_user(user["user_id"], limit=10000)}
    return [
        {
            "id": r["id"],
            "doc_id": r["doc_id"],
            "original_name": docs.get(r["doc_id"], {}).get("original_name") or r["doc_id"],
            "action": r["action"],
            "metadata": r["metadata_json"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


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
    db_log_activity(doc_id, action, user["user_id"])
    return {"status": "ok", "doc_id": doc_id, "action": action}
