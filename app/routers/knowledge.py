"""Knowledge graph endpoints for document nodes and related edges."""
from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import KnowledgeNodeResponse, KnowledgeEdgeResponse
from app.db.sqlite_store import get_document
from app.db.knowledge_store import get_latest_node, get_edges_for_source_document
from app.services.auth import require_auth

router = APIRouter()


@router.get("/knowledge/nodes/{doc_id}", response_model=KnowledgeNodeResponse)
async def get_node(doc_id: str, user: dict = Depends(require_auth)):
    """Get the latest knowledge node for a document owned by the user."""
    if not get_document(doc_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Document not found")

    node = get_latest_node(doc_id, user["user_id"])
    if not node:
        raise HTTPException(status_code=404, detail="Knowledge node not found")

    return _node_response(node)


@router.get("/knowledge/related/{doc_id}")
async def get_related(doc_id: str, user: dict = Depends(require_auth)):
    """Get related document edges for a document owned by the user."""
    if not get_document(doc_id, user["user_id"]):
        raise HTTPException(status_code=404, detail="Document not found")

    edges = get_edges_for_source_document(doc_id, user["user_id"], status="accepted")
    return {
        "source_doc_id": doc_id,
        "edges": [_edge_response(e) for e in edges],
    }


def _node_response(node: dict) -> dict:
    labels = node.get("labels_json") or []
    if isinstance(labels, str):
        labels = []
    return {
        "node_id": node["node_id"],
        "document_id": node["document_id"],
        "title": node.get("title"),
        "summary": node.get("summary"),
        "mindmap_markdown": node.get("mindmap_markdown"),
        "language": node.get("language"),
        "labels": labels,
        "internal_consistency": node["internal_consistency"],
        "evidence_coverage": node["evidence_coverage"],
        "extraction_quality": node["extraction_quality"],
        "status": node["status"],
        "version": node["version"],
        "created_at": node["created_at"],
    }


def _edge_response(edge: dict) -> dict:
    evidence = edge.get("evidence_json") or {}
    if isinstance(evidence, str):
        evidence = {}
    return {
        "edge_id": edge["edge_id"],
        "source_node_id": edge["source_node_id"],
        "source_doc_id": edge["source_document_id"],
        "target_node_id": edge["target_node_id"],
        "target_doc_id": edge["target_document_id"],
        "relation_type": edge["relation_type"],
        "similarity_score": edge["similarity_score"],
        "evidence": evidence,
        "status": edge["status"],
        "created_at": edge["created_at"],
    }
