"""Chat service: sessions, evidence retrieval, bounded generation, and persistence."""
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.db.chat_store import (
    insert_session,
    get_session,
    list_sessions,
    insert_message,
    get_messages_for_session,
)
from app.db.knowledge_store import get_edges_for_source_document
from app.db.sqlite_store import get_document
from app.models.schemas import Citation
from app.services.llm import complete
from app.services.prompts import build_chat_prompt, CHAT_PROMPT_VERSION
from app.services.retrieval import retrieve_chunks, detect_contradictions

logger = logging.getLogger(__name__)

CHAT_MAX_HISTORY_MESSAGES = 5
CHAT_MAX_CONTEXT_CHARS = 4000
CHAT_MAX_NEW_TOKENS = 768

_NO_EVIDENCE_ANSWER = "Không tìm thấy đủ bằng chứng trong các tài liệu đã tải lên."


def create_chat_session(user_id: str, doc_id: str, title: str | None = None) -> dict:
    """Create a chat session scoped to a single document owned by the user."""
    if not get_document(doc_id, user_id):
        raise ValueError("Document not found")

    session_id = uuid.uuid4().hex[:12]
    if not title:
        title = f"Chat {doc_id}"
    return insert_session(session_id, user_id, doc_id, title)


def list_chat_sessions(user_id: str, limit: int = 20, offset: int = 0) -> list[dict]:
    return list_sessions(user_id, limit, offset)


async def get_session_with_messages(user_id: str, session_id: str) -> tuple[dict, list[dict]]:
    session = get_session(session_id, user_id)
    if not session:
        raise ValueError("Session not found")
    messages = get_messages_for_session(session_id)
    return session, messages


async def post_chat_message(
    user_id: str,
    session_id: str,
    content: str,
    mode: str,
) -> dict:
    """Post a user message and generate an assistant response with evidence."""
    session = get_session(session_id, user_id)
    if not session:
        raise ValueError("Session not found")

    doc_id = session["document_id"]
    if not get_document(doc_id, user_id):
        raise ValueError("Document not found")

    related_doc_ids: list[str] = []
    related_nodes: list[dict] = []
    edges: list[dict] = []

    if mode == "document_and_related":
        edges = get_edges_for_source_document(doc_id, user_id, status="accepted")
        seen_docs: set[str] = set()
        for edge in edges:
            target_doc = edge["target_document_id"]
            if target_doc not in seen_docs:
                related_doc_ids.append(target_doc)
                seen_docs.add(target_doc)
            related_nodes.append({
                "node_id": edge["target_node_id"],
                "document_id": target_doc,
                "title": edge.get("evidence", {}).get("target_title"),
                "relation_type": edge["relation_type"],
            })
        # Deduplicate related_nodes by node_id
        seen_nodes: set[str] = set()
        unique_nodes: list[dict] = []
        for node in related_nodes:
            if node["node_id"] not in seen_nodes:
                unique_nodes.append(node)
                seen_nodes.add(node["node_id"])
        related_nodes = unique_nodes

    chunks = await retrieve_chunks(
        query=content,
        user_id=user_id,
        doc_id=doc_id,
        related_doc_ids=related_doc_ids,
        top_k=5,
    )

    warnings = detect_contradictions(chunks, content)

    if not chunks:
        answer = _NO_EVIDENCE_ANSWER
    else:
        context = _build_context(chunks)
        history = _build_history(session_id)
        prompt = build_chat_prompt(question=content, context=context, history=history)
        try:
            answer = await complete(
                prompt,
                system_prompt=_chat_system_prompt(),
                max_new_tokens=CHAT_MAX_NEW_TOKENS,
            )
        except Exception as exc:
            logger.warning("LLM chat generation failed: %s", exc)
            answer = _NO_EVIDENCE_ANSWER
            warnings.append("Mô hình tạo câu trả lờI không thành công; chỉ hiển thị bằng chứng có sẵn.")

        if not answer.strip():
            answer = _NO_EVIDENCE_ANSWER

    citations = [_chunk_to_citation(c) for c in chunks[:5]]

    insert_message(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=content,
        model_id=None,
        prompt_version=None,
    )

    related_documents = [
        {
            "doc_id": edge["target_document_id"],
            "title": edge.get("evidence", {}).get("target_title"),
            "relation_type": edge["relation_type"],
        }
        for edge in edges
    ]

    assistant_message = insert_message(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=answer,
        citations=citations,
        related_nodes=related_nodes,
        warnings=warnings,
        model_id=settings.llm_model,
        prompt_version=CHAT_PROMPT_VERSION,
    )

    return {
        "message_id": assistant_message["message_id"],
        "session_id": session_id,
        "answer": answer,
        "citations": citations,
        "related_documents": related_documents,
        "related_nodes": related_nodes,
        "warnings": warnings,
        "model_id": settings.llm_model,
        "prompt_version": CHAT_PROMPT_VERSION,
    }


def _chat_system_prompt() -> str:
    return (
        "Bạn là trợ lý học tập. Chỉ trả lờI dựa trên bằng chứng được cung cấp. "
        "Nếu thiếu bằng chứng, hãy nói rõ: 'Không tìm thấy đủ bằng chứng trong các tài liệu đã tải lên.' "
        "Nếu có mâu thuẫn, trình bày cả hai nguồn và không tự chọn bên đúng. "
        "Không thay đổi, bịa đặt, hoặc làm ảnh hưởng đến summary, quiz hay mindmap đã lưu. "
        "Trích dẫn nguồn bằng [doc_id] và trang/cảnh/thờI gian nếu có."
    )


def _build_context(chunks: list[dict]) -> str:
    parts: list[str] = []
    for chunk in chunks:
        markers: list[str] = [f"[doc_id={chunk['doc_id']}]"]
        if chunk.get("page") is not None:
            markers.append(f"[Page {chunk['page']}]")
        if chunk.get("scene") is not None:
            markers.append(f"[Scene {chunk['scene']}]")
        if chunk.get("timestamp") is not None:
            markers.append(f"[Time {chunk['timestamp']}s]")
        parts.append(" ".join(markers) + "\n" + chunk["text"])
    return "\n\n---\n\n".join(parts)[:CHAT_MAX_CONTEXT_CHARS]


def _build_history(session_id: str) -> str:
    messages = get_messages_for_session(session_id, limit=CHAT_MAX_HISTORY_MESSAGES * 2, order="desc")
    lines: list[str] = []
    total_chars = 0
    for msg in reversed(messages):
        if len(lines) >= CHAT_MAX_HISTORY_MESSAGES * 2:
            break
        line = f"{msg['role']}: {msg['content']}"
        if total_chars + len(line) > CHAT_MAX_CONTEXT_CHARS:
            break
        lines.append(line)
        total_chars += len(line)
    return "\n".join(reversed(lines))


def _chunk_to_citation(chunk: dict) -> dict:
    return Citation(
        doc_id=chunk["doc_id"],
        page=chunk.get("page"),
        scene=chunk.get("scene"),
        timestamp=chunk.get("timestamp"),
        chunk_text=chunk["text"][:500],
    ).model_dump()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
