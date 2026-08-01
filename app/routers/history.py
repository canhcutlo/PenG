from fastapi import APIRouter, HTTPException
from app.models.schemas import LearningActivity
from app.db.sqlite_store import get_activities, log_activity as db_log_activity

router = APIRouter()


@router.get("/history")
async def get_learning_history(limit: int = 20):
    """Get recent learning activities from SQLite."""
    rows = get_activities(limit)
    return [
        {
            "id": r["id"],
            "doc_id": r["doc_id"],
            "action": r["action"],
            "metadata": r["metadata_json"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


@router.post("/history")
async def log_learning_activity(doc_id: str, action: str):
    """Log a learning activity."""
    if action not in ("uploaded", "viewed", "quizzed", "mindmapped"):
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
    db_log_activity(doc_id, action)
    return {"status": "ok", "doc_id": doc_id, "action": action}
