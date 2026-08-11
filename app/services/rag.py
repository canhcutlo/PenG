"""LightRAG integration for indexing and retrieval (pinned: lightrag-hku 1.5.5).

IMPORTANT version notes (verified against lightrag-hku 1.5.5):
- Must call `await initialize_storages()` before first insert.
- Use `await ainsert(...)` / `await aquery(...)` from async code.
- Vector storage default is NanoVectorDBStorage (file-based, persistent in
  `working_dir`). ChromaDB is deprecated in this version (kg/deprecated/).
- Embedding func must return numpy arrays (`.size` is required by LightRAG).
- Query modes: "naive" (vector-only, no graph), "local", "global", "mix".
"""
import logging
from typing import Any

from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc

from app.config import settings

logger = logging.getLogger(__name__)

_rag: LightRAG | None = None
_initialized: bool = False


async def _llm_model_func(prompt: str, system_prompt: str | None = None, **kwargs) -> str:
    """LLM completion wrapper for LightRAG (falls back to fake reply)."""
    from app.services.llm import complete
    return await complete(prompt, system_prompt)


async def _embedding_func(texts: list[str]) -> list[list[float]]:
    """Embedding function wrapper for LightRAG. Returns numpy array."""
    from app.services.llm import embed
    return await embed(texts)


async def get_rag() -> LightRAG:
    """Lazily build and initialize the LightRAG instance."""
    global _rag, _initialized
    if _rag is None:
        _rag = LightRAG(
            working_dir=str(settings.lightrag_working_dir),
            llm_model_func=_llm_model_func,
            embedding_func=EmbeddingFunc(
                embedding_dim=settings.embedding_dim,
                max_token_size=512,
                func=_embedding_func,
            ),
            chunk_token_size=512,
            chunk_overlap_token_size=64,
        )
    if not _initialized:
        await _rag.initialize_storages()
        _initialized = True
    return _rag


def reset_rag_for_tests():
    """Reset the cached LightRAG instance (used by unit tests)."""
    global _rag, _initialized
    _rag = None
    _initialized = False


async def index_document(doc_id: str, text: str):
    """Index a document into LightRAG. Idempotent at storage level."""
    rag = await get_rag()
    await rag.ainsert(text, ids=[doc_id])
    logger.info("Indexed document %s", doc_id)


async def query_documents(query: str, top_k: int = 5, mode: str = "naive") -> dict[str, Any]:
    """Query LightRAG for relevant content.

    Returns {"answer": str, "citations": [...]}.
    Uses naive mode by default (vector-only) so retrieval works without a
    graph/LLM. For full RAG answers switch mode to "local"/"mix" once an LLM
    is configured.
    """
    rag = await get_rag()
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
        chunks = await _retrieve_chunks_directly(query, top_k)
        if chunks:
            answer = "Không đủ dữ liệu để trả lời đầy đủ. " \
                     "Dưới đây là các đoạn liên quan nhất:\n\n" + \
                     "\n\n---\n\n".join(chunks)
        else:
            answer = "Không tìm thấy nội dung liên quan."

    return {"answer": answer, "citations": []}


async def _retrieve_chunks_directly(query: str, top_k: int = 5) -> list[str]:
    """Directly retrieve chunks from LightRAG's vector store (no LLM needed)."""
    try:
        rag = await get_rag()
        param = QueryParam(mode="naive", top_k=top_k, chunk_top_k=top_k, enable_rerank=False, only_need_context=True)
        context = await rag.aquery(query, param=param)
        if context and "no-context" not in str(context).lower():
            return [str(context)]
    except Exception:
        pass
    return []
