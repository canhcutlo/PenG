from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.db.sqlite_store import get_document, log_activity
from app.db.artifact_store import get_latest_artifact
from app.services.file_storage import get_document_file_path
from app.services.extractor import extract, get_text_from_result
from app.services.mindmap_gen import generate_mindmap_markdown
from app.services.auth import require_auth

router = APIRouter()


class MindmapResponse(BaseModel):
    doc_id: str
    markdown: str
    source: str = "generated"


@router.get("/mindmap/{doc_id}", response_model=MindmapResponse)
async def get_mindmap(doc_id: str, user: dict = Depends(require_auth)):
    """Return a sanitized markdown mindmap for a document. Prefer stored artifact."""
    doc = get_document(doc_id, user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    artifact = get_latest_artifact(doc_id, "mindmap", status="completed")
    if artifact:
        log_activity(doc_id, "mindmapped", user["user_id"], {"source": "artifact", "artifact_id": artifact["artifact_id"]})
        return MindmapResponse(doc_id=doc_id, markdown=artifact["content"] or "", source="artifact")

    try:
        file_path = get_document_file_path(doc_id)
        result = await extract(str(file_path), doc["category"])
        text = get_text_from_result(result)
        markdown = await generate_mindmap_markdown(text)
        log_activity(doc_id, "mindmapped", user["user_id"], {"source": "generated"})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mindmap generation failed: {exc}")

    return MindmapResponse(doc_id=doc_id, markdown=markdown, source="generated")
