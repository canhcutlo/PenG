# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Knowledge graph construction from artifacts: nodes, reliability, and related edges."""
import json
import logging
import re
import uuid
from typing import Any
import numpy as np

from app.config import settings
from app.db.artifact_store import get_latest_artifact
from app.db.knowledge_store import (
    insert_node,
    get_latest_node,
    get_nodes_for_user,
    delete_edges_for_source_document,
    insert_edge,
    get_edges_for_source_document,
)
from app.db.sqlite_store import get_document
from app.services.llm import embed

logger = logging.getLogger(__name__)

KNOWLEDGE_PROMPT_VERSION = "knowledge_v1"
_EDGE_SIMILARITY_THRESHOLD = 0.55
_EDGE_SUPPORTS_THRESHOLD = 0.85


def _extract_title(mindmap_markdown: str, fallback: str = "") -> str:
    for line in mindmap_markdown.splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return fallback.strip() or "Untitled"


def _extract_labels(summary: str, mindmap_markdown: str) -> list[str]:
    labels: set[str] = set()
    for line in mindmap_markdown.splitlines():
        m = re.match(r"^##\s+(.+)$", line.strip())
        if m:
            label = _normalize_label(m.group(1))
            if label:
                labels.add(label)
    for line in summary.splitlines():
        line = line.strip()
        if line.startswith("-"):
            label = _normalize_label(line.lstrip("-").strip())
            if label:
                labels.add(label)
    return sorted(labels)[:20]


def _normalize_label(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    words = [w for w in text.split() if len(w) > 2]
    if not words:
        return ""
    return " ".join(words[:5])


def _compute_reliability(summary_artifact: dict, mindmap_artifact: dict, char_count: int) -> dict[str, Any]:
    """Deterministic reliability heuristics; not a claim of factual truth."""
    warnings: list[str] = []

    if char_count < 50:
        extraction_quality = 0.2
        warnings.append("Nội dung trích xuất quá ngắn.")
    elif char_count < 500:
        extraction_quality = 0.6
    elif char_count < 2000:
        extraction_quality = 0.8
    else:
        extraction_quality = min(1.0, 0.8 + char_count / 20000)

    summary_bullets = len([line for line in (summary_artifact.get("content") or "").splitlines() if line.strip().startswith("-")])
    mindmap_h2 = len([line for line in (mindmap_artifact.get("content") or "").splitlines() if re.match(r"^##\s+\S", line)])
    expected_coverage = max(1, char_count / 800)
    evidence_coverage = min(1.0, (summary_bullets + mindmap_h2) / expected_coverage)

    # Internal consistency: basic structural sanity; low if very few extracted markers.
    if summary_bullets >= 1 and mindmap_h2 >= 3:
        internal_consistency = 0.85
    elif summary_bullets >= 1 or mindmap_h2 >= 3:
        internal_consistency = 0.65
    else:
        internal_consistency = 0.45
        warnings.append("Cấu trúc tóm tắt hoặc mindmap không đầy đủ.")

    if extraction_quality < 0.3 or evidence_coverage < 0.2:
        status = "rejected"
    elif extraction_quality < 0.7 or evidence_coverage < 0.5 or internal_consistency < 0.6:
        status = "review_required"
    else:
        status = "accepted"

    return {
        "internal_consistency": round(internal_consistency, 3),
        "evidence_coverage": round(evidence_coverage, 3),
        "extraction_quality": round(extraction_quality, 3),
        "status": status,
        "warnings": warnings,
    }


def _relation_type(similarity: float, shared_labels: set[str]) -> str:
    if similarity >= _EDGE_SUPPORTS_THRESHOLD and shared_labels:
        return "supports"
    return "related_to"


def _cosine_similarity(query_vec: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return np.array([])
    return np.dot(vectors, query_vec) / (np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_vec) + 1e-10)


async def update_knowledge_node_from_artifacts(doc_id: str, user_id: str) -> dict | None:
    """Create or update a knowledge node using available artifacts or fallback document text."""
    summary = get_latest_artifact(doc_id, "summary", status="completed")
    mindmap = get_latest_artifact(doc_id, "mindmap", status="completed")

    if not summary and not mindmap:
        summary = get_latest_artifact(doc_id, "summary")
        mindmap = get_latest_artifact(doc_id, "mindmap")

    doc = get_document(doc_id)
    doc_name = (doc.get("original_name") or doc.get("filename") or doc_id) if doc else doc_id

    summary_content = (summary.get("content") if summary else "") or ""
    mindmap_content = (mindmap.get("content") if mindmap else "") or ""

    if not summary_content and not mindmap_content and not doc:
        return None

    if not summary_content or not mindmap_content:
        from app.db.chunk_store import get_chunks_for_doc
        chunks = get_chunks_for_doc(doc_id)
        sample_text = " ".join(c.get("text", "") for c in chunks[:5]).strip()
        if not summary_content:
            if chunks:
                summary_content = "\n".join(f"- {c['text'][:180].strip()}" for c in chunks[:5] if c.get("text"))
            else:
                summary_content = f"- Tài liệu: {doc_name}"
        if not mindmap_content:
            if sample_text:
                from app.services.mindmap_gen import build_fallback_mindmap
                mindmap_content = build_fallback_mindmap(sample_text, fallback_title=doc_name)
            else:
                mindmap_content = f"# {doc_name}\n## Nội dung\n- Thông tin tài liệu\n- Đang xử lý"

    dummy_summary = summary or {"artifact_id": f"fallback-summary-{doc_id}", "content": summary_content, "doc_id": doc_id, "input_snapshot": {}}
    dummy_mindmap = mindmap or {"artifact_id": f"fallback-mindmap-{doc_id}", "content": mindmap_content, "doc_id": doc_id}

    title = _extract_title(mindmap_content, fallback=doc_name)
    labels = _extract_labels(summary_content, mindmap_content)
    if not labels and doc_name:
        norm = _normalize_label(doc_name)
        if norm:
            labels = [norm]

    char_count = (summary.get("input_snapshot", {}) if summary else {}).get("char_count", len(summary_content))
    reliability = _compute_reliability(dummy_summary, dummy_mindmap, char_count)

    previous = get_latest_node(doc_id, user_id)
    version = (previous["version"] + 1) if previous else 1

    node_id = uuid.uuid4().hex[:12]
    node = insert_node(
        node_id=node_id,
        user_id=user_id,
        document_id=doc_id,
        title=title,
        summary=summary_content,
        mindmap_markdown=mindmap_content,
        language=(summary.get("language") if summary else None) or (mindmap.get("language") if mindmap else None) or "vi",
        labels=labels,
        internal_consistency=reliability["internal_consistency"],
        evidence_coverage=reliability["evidence_coverage"],
        extraction_quality=reliability["extraction_quality"],
        status=reliability["status"],
        version=version,
        input_snapshot={
            "summary_artifact_id": dummy_summary.get("artifact_id", "fallback"),
            "mindmap_artifact_id": dummy_mindmap.get("artifact_id", "fallback"),
            "source_text_char_count": char_count,
            "reliability_warnings": reliability["warnings"],
        },
        model_id=settings.llm_model,
        prompt_version=KNOWLEDGE_PROMPT_VERSION,
    )

    try:
        await build_related_edges_for_user(user_id, doc_id)
    except Exception as exc:
        logger.warning("Failed to build related edges for %s: %s", doc_id, exc)

    return node


async def build_related_edges_for_user(user_id: str, source_document_id: str, top_k: int = 5) -> list[dict]:
    """Build deterministic related edges for a document against other documents of the same user."""
    source_node = get_latest_node(source_document_id, user_id)
    if not source_node:
        return []

    target_nodes = [
        n for n in get_nodes_for_user(user_id)
        if n["document_id"] != source_document_id and n["status"] == "accepted"
    ]
    if not target_nodes:
        return []

    source_text = _node_embedding_text(source_node)
    target_texts = [_node_embedding_text(n) for n in target_nodes]

    try:
        embeddings = await embed([source_text] + target_texts)
    except Exception as exc:
        logger.warning("Embedding failed during edge building: %s", exc)
        return []

    source_vec = embeddings[0]
    target_vecs = embeddings[1:]
    scores = _cosine_similarity(source_vec, target_vecs)

    delete_edges_for_source_document(source_document_id, user_id)

    edges: list[dict] = []
    source_labels = _labels_to_set(source_node.get("labels_json"))
    for idx, target in enumerate(target_nodes):
        score = float(scores[idx])
        if score < _EDGE_SIMILARITY_THRESHOLD:
            continue
        target_labels = _labels_to_set(target.get("labels_json"))
        shared = source_labels & target_labels
        relation_type = _relation_type(score, shared)
        evidence = {
            "source_title": source_node.get("title"),
            "target_title": target.get("title"),
            "shared_labels": sorted(shared),
            "similarity_method": "cosine_embedding",
        }
        edge_id = uuid.uuid4().hex[:12]
        edge = insert_edge(
            edge_id=edge_id,
            user_id=user_id,
            source_node_id=source_node["node_id"],
            target_node_id=target["node_id"],
            source_document_id=source_document_id,
            target_document_id=target["document_id"],
            relation_type=relation_type,
            similarity_score=score,
            evidence=evidence,
            status="accepted",
        )
        edges.append(edge)

    return sorted(edges, key=lambda e: e["similarity_score"], reverse=True)[:top_k]


def _labels_to_set(labels: Any) -> set[str]:
    if isinstance(labels, str):
        labels = json.loads(labels)
    if not labels:
        return set()
    return set(labels)


def _node_embedding_text(node: dict) -> str:
    parts = [node.get("title") or "", node.get("summary") or ""]
    labels = _labels_to_set(node.get("labels_json"))
    if labels:
        parts.append(" ".join(labels))
    return " ".join(parts)


def get_owned_knowledge_node(doc_id: str, user_id: str) -> dict | None:
    if not get_document(doc_id, user_id):
        raise LookupError("Document not found")
    return get_latest_node(doc_id, user_id)


def get_owned_related_edges(doc_id: str, user_id: str) -> list[dict]:
    if not get_document(doc_id, user_id):
        raise LookupError("Document not found")
    return get_edges_for_source_document(doc_id, user_id, status="accepted")
