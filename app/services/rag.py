"""LightRAG integration for indexing and retrieval (pinned: lightrag-hku 1.5.5).

Per-user working directories isolate RAG data between accounts.
"""
import logging
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

from app.config import settings

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


async def query_documents(query: str, top_k: int = 5, mode: str = "naive", user_id: str | None = None) -> dict[str, Any]:
    """Query LightRAG for relevant content.

    Returns {"answer": str, "citations": [...]}.
    Uses naive mode by default (vector-only) so retrieval works without a graph.
    """
    if not user_id:
        raise ValueError("user_id is required for RAG query")

    rag = await get_rag(user_id)
    param = QueryParam(
        mode=mode,
        top_k=top_k,
        chunk_top_k=top_k,
        enable_rerank=False,
        include_references=True,
    )
    raw = await rag.aquery(query, param=param)
    answer = str(raw or "")

    if "no-context" in answer.lower() or not answer.strip():
        chunks = await _retrieve_chunks_directly(query, top_k, user_id)
        if chunks:
            answer = "Không đủ dữ liệu để trả lờI đầy đủ. " \
                     "Dưới đây là các đoạn liên quan nhất:\n\n" + \
                     "\n\n---\n\n".join(chunks)
        else:
            answer = "Không tìm thấy nội dung liên quan."

    return {"answer": answer, "citations": []}


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
