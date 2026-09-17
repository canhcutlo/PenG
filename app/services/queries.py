# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Owned RAG query orchestration."""
from app.db.sqlite_store import get_document, log_activity
from app.models.schemas import QueryResponse, QueryResult
from app.services.rag import query_documents


async def query_owned_documents(query: str, top_k: int, doc_id: str, user_id: str) -> QueryResponse:
    if doc_id and not get_document(doc_id, user_id):
        raise LookupError(f"Document {doc_id} not found")
    result = await query_documents(
        query,
        top_k=top_k,
        mode="naive",
        user_id=user_id,
        doc_id=doc_id or None,
    )
    answer = result.get("answer", "")
    if doc_id:
        log_activity(doc_id, "viewed", user_id, {"query": query, "answer_length": len(answer)})
    return QueryResponse(
        answer=answer,
        citations=result.get("citations", [])[:5],
        related_chunks=[
            QueryResult(**chunk) if isinstance(chunk, dict) else QueryResult(
                doc_id="", chunk=str(chunk), score=0.0, source="unknown"
            )
            for chunk in result.get("related_chunks", [])
        ],
    )
