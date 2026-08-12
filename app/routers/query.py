from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import QueryResponse, QueryResult
from app.services.rag import query_documents
from app.db.sqlite_store import log_activity, get_document
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

    if doc_id:
        doc = get_document(doc_id, user["user_id"])
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    try:
        result = await query_documents(
            q.strip(),
            top_k=top_k,
            mode="naive",
            user_id=user["user_id"],
            doc_id=doc_id or None,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")

    answer = result.get("answer", "")
    citations = result.get("citations", [])
    related = result.get("related_chunks", [])

    if doc_id:
        log_activity(doc_id, "viewed", user["user_id"], {"query": q, "answer_length": len(answer)})

    return QueryResponse(
        answer=answer,
        citations=citations[:5],
        related_chunks=[
            QueryResult(**c) if isinstance(c, dict) else QueryResult(
                doc_id="", chunk=str(c), score=0.0, source="unknown"
            )
            for c in related
        ],
    )
