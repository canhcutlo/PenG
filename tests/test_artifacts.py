"""Tests for document artifacts: summary, mindmap, regeneration, versioning."""
import pytest
import io
import json
from fastapi.testclient import TestClient
from app.main import app
from app.services.artifacts import regenerate_artifact
from app.services.mindmap_gen import validate_mindmap_structure, sanitize_mindmap
from app.services.summary_gen import validate_summary_markdown
from app.db.artifact_store import get_latest_artifact, get_artifacts_by_doc
from app.db.sqlite_store import insert_document
from tests.conftest import get_auth_user_id

client = TestClient(app)




def test_mindmap_validation_accepts_valid():
    md = "# A\n## B\n- b1\n- b2\n## C\n- c1\n- c2\n## D\n- d1\n- d2"
    assert validate_mindmap_structure(md)


def test_mindmap_validation_rejects_too_few_h2():
    md = "# A\n## B\n- b1\n- b2"
    assert not validate_mindmap_structure(md)


def test_mindmap_validation_rejects_wrong_bullet_count():
    md = "# A\n## B\n- b1\n## C\n- c1\n- c2\n## D\n- d1\n- d2"
    assert not validate_mindmap_structure(md)


def test_sanitize_mindmap_removes_html_and_fences():
    raw = "# A\n<script>alert(1)</script>\n```py\ncode\n```\n#### deep"
    out = sanitize_mindmap(raw)
    assert "<script>" not in out
    assert "```" not in out
    assert "####" not in out


def test_summary_validation_accepts_valid():
    md = "- Ý 1\n- Ý 2"
    assert validate_summary_markdown(md)


def test_summary_validation_rejects_empty():
    assert not validate_summary_markdown("")




@pytest.mark.asyncio
async def test_regenerate_summary_artifact(monkeypatch, auth_client):
    doc_id = "art_doc_summary"
    user_id = get_auth_user_id(auth_client)
    insert_document(doc_id, "fake.pdf", "fake.pdf", "pdf", 100, "art_hash", user_id)

    async def fake_summary(text, max_retries=3):
        return "- Bullet one\n- Bullet two"

    async def fake_get_text(doc_id):
        return "nội dung mẫu"

    monkeypatch.setattr("app.services.artifacts.generate_summary", fake_summary)
    monkeypatch.setattr("app.services.artifacts._get_document_text", fake_get_text)

    artifact = await regenerate_artifact(doc_id, user_id, "summary")
    assert artifact["type"] == "summary"
    assert artifact["status"] == "completed"
    assert artifact["version"] == 1
    assert "- Bullet one" in artifact["content"]


@pytest.mark.asyncio
async def test_regenerate_mindmap_artifact(monkeypatch, auth_client):
    doc_id = "art_doc_mindmap"
    user_id = get_auth_user_id(auth_client)
    insert_document(doc_id, "fake.pdf", "fake.pdf", "pdf", 100, "art_hash2", user_id)

    async def fake_mindmap(text):
        return "# Chủ đề\n## Nhánh 1\n- Ý 1\n- Ý 2\n## Nhánh 2\n- Ý 3\n- Ý 4\n## Nhánh 3\n- Ý 5\n- Ý 6"

    async def fake_get_text(doc_id):
        return "nội dung mẫu"

    monkeypatch.setattr("app.services.artifacts.generate_mindmap_markdown", fake_mindmap)
    monkeypatch.setattr("app.services.artifacts._get_document_text", fake_get_text)

    artifact = await regenerate_artifact(doc_id, user_id, "mindmap")
    assert artifact["type"] == "mindmap"
    assert artifact["status"] == "completed"
    assert artifact["version"] == 1


@pytest.mark.asyncio
async def test_artifact_failure_preserves_old(monkeypatch, auth_client):
    doc_id = "art_doc_fail"
    user_id = get_auth_user_id(auth_client)
    insert_document(doc_id, "fake.pdf", "fake.pdf", "pdf", 100, "art_hash3", user_id)

    async def fake_summary(text, max_retries=3):
        return "- Bullet one"

    async def fake_summary_fail(text, max_retries=3):
        raise ValueError("boom")

    async def fake_get_text(doc_id):
        return "nội dung mẫu"

    monkeypatch.setattr("app.services.artifacts._get_document_text", fake_get_text)
    monkeypatch.setattr("app.services.artifacts.generate_summary", fake_summary)
    first = await regenerate_artifact(doc_id, user_id, "summary")
    assert first["status"] == "completed"

    monkeypatch.setattr("app.services.artifacts.generate_summary", fake_summary_fail)
    second = await regenerate_artifact(doc_id, user_id, "summary")
    assert second["status"] == "failed"

    latest = get_latest_artifact(doc_id, "summary", status="completed")
    assert latest is not None
    assert latest["artifact_id"] == first["artifact_id"]




def test_documents_list_requires_auth():
    resp = client.get("/api/documents")
    assert resp.status_code == 401


def test_documents_list_returns_owned(auth_client):
    content = b"\x89PNG\r\n\x1a\n" + b"listdoc" + b"\x00" * 50
    auth_client.post(
        "/api/upload",
        files={"file": ("list.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )

    resp = auth_client.get("/api/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert any(d["filename"] == "list.png" for d in data)


def test_summary_endpoint_returns_artifact(auth_client, monkeypatch):
    import uuid
    doc_id = uuid.uuid4().hex[:12]
    user_id = get_auth_user_id(auth_client)
    insert_document(doc_id, "fake.pdf", "fake.pdf", "pdf", 100, "sum_hash", user_id)

    async def fake_summary(text, max_retries=3):
        return "- Bullet one\n- Bullet two"

    async def fake_get_text(doc_id):
        return "nội dung mẫu"

    monkeypatch.setattr("app.services.artifacts.generate_summary", fake_summary)
    monkeypatch.setattr("app.services.artifacts._get_document_text", fake_get_text)

    resp = auth_client.post(f"/api/documents/{doc_id}/artifacts/regenerate?artifact_type=summary")
    assert resp.status_code == 200

    resp2 = auth_client.get(f"/api/documents/{doc_id}/summary")
    assert resp2.status_code == 200
    assert "Bullet one" in resp2.json()["content"]
