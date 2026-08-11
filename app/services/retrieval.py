"""Evidence retrieval for chat: chunks with real metadata and deterministic scoring."""
import logging
import numpy as np
from app.db.chunk_store import get_chunks_for_doc, get_chunks_for_docs
from app.services.llm import embed

logger = logging.getLogger(__name__)


def _cosine_similarity(query_vec: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return np.array([])
    return np.dot(vectors, query_vec) / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_vec) + 1e-10)


async def retrieve_chunks(
    query: str,
    user_id: str,
    doc_id: str | None = None,
    related_doc_ids: list[str] | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Retrieve top-k chunks for a query, scoped to a document and optionally related docs."""
    candidates: list[dict] = []
    seen: set[str] = set()

    if doc_id:
        for chunk in get_chunks_for_doc(doc_id, user_id):
            if chunk["chunk_id"] not in seen:
                candidates.append(chunk)
                seen.add(chunk["chunk_id"])

    related = related_doc_ids or []
    if related:
        for chunk in get_chunks_for_docs(related, user_id):
            if chunk["chunk_id"] not in seen:
                candidates.append(chunk)
                seen.add(chunk["chunk_id"])

    if not candidates:
        return []

    try:
        embeddings = await embed([query] + [c["text"] for c in candidates])
    except Exception as exc:
        logger.warning("Embedding failed during retrieval: %s", exc)
        return candidates[:top_k]

    if embeddings.shape[0] != len(candidates) + 1:
        return candidates[:top_k]

    query_vec = embeddings[0]
    chunk_vecs = embeddings[1:]
    scores = _cosine_similarity(query_vec, chunk_vecs)

    scored = [(float(scores[i]), candidates[i]) for i in range(len(candidates))]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]


_NEGATION_WORDS = {"không", "not", "no", "never"}


def detect_contradictions(chunks: list[dict], query: str) -> list[str]:
    """Simple deterministic contradiction check between top chunks."""
    warnings: list[str] = []
    if len(chunks) < 2:
        return warnings

    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    if not query_terms:
        return warnings

    positive_hits: list[str] = []
    negative_hits: list[str] = []

    for chunk in chunks:
        text = chunk["text"].lower()
        for term in query_terms:
            if term not in text:
                continue
            # Check for a negation word near the term
            idx = text.find(term)
            window = text[max(0, idx - 30):idx + 30]
            if any(neg in window for neg in _NEGATION_WORDS):
                negative_hits.append(chunk["text"][:120])
            else:
                positive_hits.append(chunk["text"][:120])

    if positive_hits and negative_hits:
        warnings.append(
            "Phát hiện mâu thuẫn trong bằng chứng; xem xét cả hai nguồn trước khi kết luận."
        )
    return warnings
