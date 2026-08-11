"""Tests for Phase 10: chat, knowledge nodes, edges, and evidence retrieval."""
import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.sqlite_store import insert_document
from app.db.artifact_store import insert_artifact
from app.db.chunk_store import insert_chunks
from app.db.knowledge_store import get_latest_node, get_edges_for_source_document
from app.services.chat import (
    create_chat_session,
    post_chat_message,
    _build_history,
    CHAT_MAX_HISTORY_MESSAGES,
)
from app.services.knowledge import update_knowledge_node_from_artifacts, build_related_edges_for_user
from tests.conftest import get_auth_user_id
from tests.test_rag import FakeEmbedding


client = TestClient(app)


async def _fake_embed(texts):
    return FakeEmbedding(dim=768).encode(texts)


def _make_user_client(username: str) -> TestClient:
    c = TestClient(app)
    c.post("/api/auth/register", json={"username": username, "password": "securepass123"})
    r = c.post("/api/auth/login", json={"username": username, "password": "securepass123"})
    c.cookies.update(r.cookies)
    c.headers["X-CSRF-Token"] = r.cookies.get("peng_csrf")
    return c


def _make_doc_for_client(c: TestClient, doc_id: str | None = None, category: str = "pdf"):
    if doc_id is None:
        doc_id = uuid.uuid4().hex[:12]
    user_id = get_auth_user_id(c)
    insert_document(doc_id, "f.pdf", "f.pdf", category, 100, uuid.uuid4().hex[:16], user_id)
    return doc_id


def _make_artifact(doc_id: str, user_id: str, artifact_type: str, content: str, char_count: int = 2000):
    aid = uuid.uuid4().hex[:12]
    insert_artifact(
        artifact_id=aid,
        doc_id=doc_id,
        user_id=user_id,
        artifact_type=artifact_type,
        version=1,
        status="completed",
        content=content,
        input_snapshot={"char_count": char_count, "truncated": False, "source_job": "extract"},
        prompt_version="v1",
    )


def _make_chunks(doc_id: str, user_id: str, texts: list[str], pages: list[int | None] | None = None):
    pages = pages or [None] * len(texts)
    chunks = []
    for i, text in enumerate(texts):
        chunks.append({
            "chunk_id": f"{doc_id}:{i}",
            "doc_id": doc_id,
            "text": text,
            "page": pages[i],
            "scene": None,
            "timestamp": None,
            "metadata": {"category": "pdf"},
        })
    insert_chunks(chunks, user_id)



def test_chat_endpoints_require_auth():
    resp = client.post("/api/chat/sessions", json={"doc_id": "x"})
    assert resp.status_code == 401
    resp = client.post("/api/chat/abc/messages", json={"content": "hi"})
    assert resp.status_code == 401
    resp = client.get("/api/chat/sessions")
    assert resp.status_code == 401


def test_create_session_requires_csrf(auth_client):
    c2 = TestClient(app)
    c2.cookies.update(auth_client.cookies)
    resp = c2.post("/api/chat/sessions", json={"doc_id": "x"})
    assert resp.status_code == 403


def test_chat_session_ownership_isolation(auth_client):
    doc_id = _make_doc_for_client(auth_client)
    resp = auth_client.post("/api/chat/sessions", json={"doc_id": doc_id, "title": "A session"})
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    c_b = _make_user_client(f"chatuserb_{uuid.uuid4().hex[:6]}")
    assert c_b.get(f"/api/chat/{session_id}").status_code == 404
    assert c_b.post(f"/api/chat/{session_id}/messages", json={"content": "hello"}).status_code == 404



@pytest.mark.asyncio
async def test_knowledge_node_ownership_isolation(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.knowledge.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    _make_artifact(doc_id, user_id, "summary", "- Bullet", 2000)
    _make_artifact(doc_id, user_id, "mindmap", "# T\n## A\n- a1\n- a2\n## B\n- b1\n- b2\n## C\n- c1\n- c2", 2000)

    node = await update_knowledge_node_from_artifacts(doc_id, user_id)
    assert node is not None

    c_b = _make_user_client(f"kuserb_{uuid.uuid4().hex[:6]}")
    assert c_b.get(f"/api/knowledge/nodes/{doc_id}").status_code == 404
    assert c_b.get(f"/api/knowledge/related/{doc_id}").status_code == 404


@pytest.mark.asyncio
async def test_chat_no_context_returns_no_evidence(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    session = create_chat_session(user_id, doc_id)
    result = await post_chat_message(user_id, session["session_id"], "sao Hỏa", "document_and_related")
    assert result["answer"] == "Không tìm thấy đủ bằng chứng trong các tài liệu đã tải lên."
    assert result["citations"] == []


@pytest.mark.asyncio
async def test_chat_citations_are_real(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    _make_chunks(doc_id, user_id, ["Hà Nội là thủ đô của Việt Nam."], pages=[1])
    session = create_chat_session(user_id, doc_id)
    result = await post_chat_message(user_id, session["session_id"], "thủ đô Việt Nam", "document_and_related")
    assert result["citations"]
    for citation in result["citations"]:
        assert citation["doc_id"] == doc_id
        assert "Hà Nội" in citation["chunk_text"]
        assert citation.get("page") == 1
        assert citation.get("scene") is None


@pytest.mark.asyncio
async def test_chat_related_retrieval(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    monkeypatch.setattr("app.services.knowledge.embed", _fake_embed)
    doc_a = _make_doc_for_client(auth_client)
    doc_b = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)

    _make_chunks(doc_a, user_id, ["Tài liệu A về machine learning."], pages=[1])
    _make_chunks(doc_b, user_id, ["Tài liệu B về machine learning nâng cao."], pages=[1])

    _make_artifact(doc_a, user_id, "summary", "- machine learning cơ bản", 2000)
    _make_artifact(doc_a, user_id, "mindmap", "# A\n## ML\n- a1\n- a2\n## B\n- b1\n- b2\n## C\n- c1\n- c2", 2000)
    _make_artifact(doc_b, user_id, "summary", "- machine learning nâng cao", 2000)
    _make_artifact(doc_b, user_id, "mindmap", "# B\n## ML\n- b1\n- b2\n## C\n- c1\n- c2\n## D\n- d1\n- d2", 2000)

    await update_knowledge_node_from_artifacts(doc_a, user_id)
    await update_knowledge_node_from_artifacts(doc_b, user_id)
    edges = await build_related_edges_for_user(user_id, doc_a)
    assert len(edges) > 0

    session = create_chat_session(user_id, doc_a)
    result = await post_chat_message(user_id, session["session_id"], "machine learning", "document_and_related")

    cited_doc_ids = {c["doc_id"] for c in result["citations"]}
    assert doc_b in cited_doc_ids
    related_doc_ids = {rd["doc_id"] for rd in result["related_documents"]}
    assert doc_b in related_doc_ids


@pytest.mark.asyncio
async def test_chat_contradiction_warning(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    _make_chunks(doc_id, user_id, [
        "Hà Nội là thủ đô của Việt Nam.",
        "Hà Nội không phải là thủ đô của Việt Nam.",
    ], pages=[1, 2])
    session = create_chat_session(user_id, doc_id)
    result = await post_chat_message(user_id, session["session_id"], "thủ đô Việt Nam", "document_and_related")
    assert any("mâu thuẫn" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_chat_context_limit_truncates_history(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    _make_chunks(doc_id, user_id, ["nội dung"], pages=[1])
    session = create_chat_session(user_id, doc_id)
    for i in range(CHAT_MAX_HISTORY_MESSAGES + 3):
        await post_chat_message(user_id, session["session_id"], f"câu hỏi {i}", "document_and_related")
    history = _build_history(session["session_id"])
    assert history.count("user:") <= CHAT_MAX_HISTORY_MESSAGES


@pytest.mark.asyncio
async def test_chat_does_not_modify_artifacts(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    summary_content = "- Bullet one\n- Bullet two"
    mindmap_content = "# Title\n## A\n- a1\n- a2\n## B\n- b1\n- b2\n## C\n- c1\n- c2"
    _make_artifact(doc_id, user_id, "summary", summary_content, 2000)
    _make_artifact(doc_id, user_id, "mindmap", mindmap_content, 2000)
    _make_chunks(doc_id, user_id, ["some content"], pages=[1])
    await update_knowledge_node_from_artifacts(doc_id, user_id)

    from app.db.artifact_store import get_latest_artifact
    session = create_chat_session(user_id, doc_id)
    await post_chat_message(user_id, session["session_id"], "some content", "document_and_related")

    assert get_latest_artifact(doc_id, "summary", status="completed")["content"] == summary_content
    assert get_latest_artifact(doc_id, "mindmap", status="completed")["content"] == mindmap_content


@pytest.mark.asyncio
async def test_knowledge_node_created_from_artifacts(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.knowledge.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    _make_artifact(doc_id, user_id, "summary", "- Bullet one\n- Bullet two", 2000)
    _make_artifact(doc_id, user_id, "mindmap", "# Title\n## Alpha\n- a1\n- a2\n## Beta\n- b1\n- b2\n## Gamma\n- c1\n- c2", 2000)

    node = await update_knowledge_node_from_artifacts(doc_id, user_id)
    assert node is not None
    assert node["document_id"] == doc_id
    assert node["title"] == "Title"
    labels = [l.lower() for l in node["labels_json"]]
    assert "alpha" in labels
    assert 0 <= node["internal_consistency"] <= 1
    assert 0 <= node["evidence_coverage"] <= 1
    assert 0 <= node["extraction_quality"] <= 1
    assert node["status"] in ("accepted", "review_required", "rejected")


@pytest.mark.asyncio
async def test_knowledge_edges_no_cross_user(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.knowledge.embed", _fake_embed)
    doc_a = _make_doc_for_client(auth_client)
    user_a = get_auth_user_id(auth_client)

    c_b = _make_user_client(f"edgeb_{uuid.uuid4().hex[:6]}")
    doc_b = _make_doc_for_client(c_b)
    user_b = get_auth_user_id(c_b)

    _make_artifact(doc_a, user_a, "summary", "- machine learning", 2000)
    _make_artifact(doc_a, user_a, "mindmap", "# A\n## ML\n- a1\n- a2\n## B\n- b1\n- b2\n## C\n- c1\n- c2", 2000)
    _make_artifact(doc_b, user_b, "summary", "- machine learning", 2000)
    _make_artifact(doc_b, user_b, "mindmap", "# B\n## ML\n- b1\n- b2\n## C\n- c1\n- c2\n## D\n- d1\n- d2", 2000)

    await update_knowledge_node_from_artifacts(doc_a, user_a)
    await update_knowledge_node_from_artifacts(doc_b, user_b)

    edges = await build_related_edges_for_user(user_a, doc_a)
    assert not any(e["target_document_id"] == doc_b for e in edges)
    for edge in edges:
        assert edge["user_id"] == user_a


@pytest.mark.asyncio
async def test_knowledge_node_status_review_for_low_quality(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.knowledge.embed", _fake_embed)
    doc_id = _make_doc_for_client(auth_client)
    user_id = get_auth_user_id(auth_client)
    _make_artifact(doc_id, user_id, "summary", "- Bullet", 30)
    _make_artifact(doc_id, user_id, "mindmap", "# T\n## A\n- a1", 30)
    node = await update_knowledge_node_from_artifacts(doc_id, user_id)
    assert node["status"] in ("review_required", "rejected")
