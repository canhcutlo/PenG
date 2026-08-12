"""LightRAG integration for indexing and retrieval (pinned: lightrag-hku 1.5.5).

Per-user working directories isolate RAG data between accounts.
"""
import logging
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

from app.config import settings
from app.models.schemas import QueryResult
from app.services.retrieval import retrieve_chunks
from app.services.faithfulness import (
    EvidenceItem,
    evidence_item_to_citation,
    generate_faithful_answer,
    normalize_evidence,
)

logger = logging.getLogger(__name__)

_rag_instances: dict[str, LightRAG] = {}
_initialized: dict[str, bool] = {}


async def _llm_model_func(prompt: str, system_prompt: str | None = None, **kwargs) -> str:
    """LLM completion wrapper for LightRAG."""
    from app.services.llm import complete
    return await complete(prompt, system_prompt)


async def _embedding_func(texts: list[str]) -> list[list[float]]:
    """Embedding function wrapper for LightRAG. Returns numpy array."""
    from app.services.llm import embed
    return await embed(texts)


def _user_working_dir(user_id: str) -> str:
    return str(settings.lightrag_working_dir / "u" / user_id)


async def get_rag(user_id: str) -> LightRAG:
    """Lazily build and initialize the LightRAG instance for a user."""
    if user_id not in _rag_instances:
        working_dir = _user_working_dir(user_id)
        _rag_instances[user_id] = LightRAG(
            working_dir=working_dir,
            llm_model_func=_llm_model_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=settings.embedding_dim,
                max_token_size=512,
                func=_embedding_func,
            ),
            chunk_token_size=512,
            chunk_overlap_token_size=64,
        )
    if not _initialized.get(user_id):
        await _rag_instances[user_id].initialize_storages()
        _initialized[user_id] = True
    return _rag_instances[user_id]


def reset_rag_for_tests():
    """Reset the cached LightRAG instances (used by unit tests)."""
    global _rag_instances, _initialized
    _rag_instances = {}
    _initialized = {}


async def index_document(doc_id: str, text: str, user_id: str):
    """Index a document into LightRAG for a user. Idempotent at storage level."""
    rag = await get_rag(user_id)
    await rag.ainsert(text, ids=[doc_id])
    logger.info("Indexed document %s for user %s", doc_id, user_id)


async def query_documents(
    query: str,
    top_k: int = 5,
    mode: str = "naive",
    user_id: str | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Query indexed documents and return a faithfulness-guarded answer.

    Returns {"answer": str, "citations": [Citation, ...], "related_chunks": [...]}.
    Retrieval is scoped to the user and optional document.
    """
    if not user_id:
        raise ValueError("user_id is required for RAG query")

    chunks = await retrieve_chunks(
        query=query, user_id=user_id, doc_id=doc_id, top_k=top_k
    )
    evidence = normalize_evidence(chunks)
    faithful = await generate_faithful_answer(query, evidence, history="")

    id_to_item = {item.id: item for item in evidence}
    cited_items: list[EvidenceItem] = [
        id_to_item[eid] for eid in faithful.evidence_ids if eid in id_to_item
    ]

    citations = [evidence_item_to_citation(item) for item in cited_items]
    related_chunks = [
        QueryResult(
            doc_id=item.doc_id,
            chunk=item.text,
            score=item.score,
            source=_evidence_source(item),
        )
        for item in evidence
    ]

    return {
        "answer": faithful.answer,
        "citations": citations,
        "related_chunks": related_chunks,
    }


def _evidence_source(item: EvidenceItem) -> str:
    if item.page is not None:
        return f"page:{item.page}"
    if item.scene is not None:
        return f"scene:{item.scene}"
    if item.timestamp is not None:
        return f"time:{item.timestamp}s"
    return "document"


async def _retrieve_chunks_directly(query: str, top_k: int, user_id: str) -> list[str]:
    """Directly retrieve chunks from LightRAG's vector store (no LLM needed)."""
    try:
        rag = await get_rag(user_id)
        param = QueryParam(mode="naive", top_k=top_k, chunk_top_k=top_k, enable_rerank=False, only_need_context=True)
        context = await rag.aquery(query, param=param)
        if context and "no-context" not in str(context).lower():
            return [str(context)]
    except Exception:
        pass
    return []
