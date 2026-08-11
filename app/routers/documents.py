"""Document listing and artifact endpoints."""
from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import Artifact
from app.db.sqlite_store import get_document, get_documents_for_user
from app.db.artifact_store import get_artifacts_by_doc, get_latest_artifact
from app.services.artifacts import regenerate_artifact
from app.services.auth import require_auth, verify_csrf

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
