from fastapi import APIRouter, HTTPException
from app.models.schemas import QueryResponse, Citation, QueryResult
from app.services.rag import query_documents
from app.db.sqlite_store import log_activity

router = APIRouter()


@router.get("/query", response_model=QueryResponse)
async def query_materials(q: str, top_k: int = 5, doc_id: str = ""):
    """Query indexed learning materials via LightRAG and return answer with citations."""
    if not q.strip():
        return QueryResponse(answer="", citations=[], related_chunks=[])

    try:
        result = await query_documents(q.strip(), top_k=top_k, mode="naive")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Query failed: {exc}")

    answer = result.get("answer", "")
    citations = _extract_citations(answer, doc_id or None)
    related = result.get("related_chunks", [])

    if doc_id:
        log_activity(doc_id, "viewed", {"query": q, "answer_length": len(answer)})

    return QueryResponse(
        answer=answer,
        citations=citations[:5],
        related_chunks=[QueryResult(**c) if isinstance(c, dict) else QueryResult(doc_id="", chunk=str(c), score=0.0, source="unknown") for c in related],
    )


def _extract_citations(answer: str, doc_id: str | None = None) -> list[Citation]:
    """Parse citation hints from LLM answer text."""
    citations: list[Citation] = []
    for line in answer.splitlines():
        line = line.strip()
        if line and ("[Page" in line or "[Scene" in line or "source:" in line.lower()):
            citations.append(
                Citation(
                    doc_id=doc_id or "unknown",
                    chunk_text=line[:200],
                )
            )
    return citations
