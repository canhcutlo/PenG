# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Tests for protected document source and original content endpoints."""
import uuid

from app.config import settings
from app.db.chunk_store import get_source_chunk_by_locator, init_chunk_tables, insert_chunks
from app.db.sqlite_store import insert_document
from tests.conftest import get_auth_user_id


def _document(auth_client, category: str = "pdf") -> tuple[str, str]:
    doc_id = uuid.uuid4().hex[:12]
    user_id = get_auth_user_id(auth_client)
    insert_document(doc_id, "stored.pdf", "lesson.pdf", category, 20, uuid.uuid4().hex, user_id)
    return doc_id, user_id


def test_document_source_list_exact_and_locators(auth_client):
    doc_id, user_id = _document(auth_client)
    chunks = [
        {"chunk_id": f"{doc_id}:a", "doc_id": doc_id, "text": "Page one", "page": 1, "timestamp": 5.0},
        {"chunk_id": f"{doc_id}:b", "doc_id": doc_id, "text": "Page two", "page": 2, "scene": 3, "timestamp": 12.0},
    ]
    insert_chunks(chunks, user_id)

    response = auth_client.get(f"/api/documents/{doc_id}/source?limit=1&offset=1")
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["chunks"][0]["chunk_id"] == f"{doc_id}:b"
    assert response.json()["chunks"][0]["position"] == 1

    response = auth_client.get(f"/api/documents/{doc_id}/source/{doc_id}:a")
    assert response.status_code == 200
    assert response.json()["text"] == "Page one"
    response = auth_client.get(f"/api/documents/{doc_id}/source?limit=1&page=2")
    assert response.status_code == 200
    assert response.json()["offset"] == 1
    assert response.json()["chunks"][0]["chunk_id"] == f"{doc_id}:b"
    assert get_source_chunk_by_locator(doc_id, user_id, page=2)["chunk_id"] == f"{doc_id}:b"
    assert get_source_chunk_by_locator(doc_id, user_id, scene=3)["chunk_id"] == f"{doc_id}:b"
    assert get_source_chunk_by_locator(doc_id, user_id, timestamp=10.0)["chunk_id"] == f"{doc_id}:b"


def test_document_source_requires_ownership(auth_client):
    doc_id, user_id = _document(auth_client)
    insert_chunks([{"chunk_id": f"{doc_id}:0", "doc_id": doc_id, "text": "private"}], user_id)
    from fastapi.testclient import TestClient
    from app.main import app

    other = TestClient(app)
    name = f"source_other_{uuid.uuid4().hex[:6]}"
    other.post("/api/auth/register", json={"username": name, "password": "securepass123"})
    other.post("/api/auth/login", json={"username": name, "password": "securepass123"})
    assert other.get(f"/api/documents/{doc_id}/source").status_code == 404
    assert other.get(f"/api/documents/{doc_id}/source/{doc_id}:0").status_code == 404
    assert other.get(f"/api/documents/{doc_id}/original").status_code == 404


def test_original_content_is_inline_and_private(auth_client):
    doc_id, _ = _document(auth_client)
    doc_dir = settings.upload_dir / doc_id
    doc_dir.mkdir(parents=True)
    payload = b"%PDF-1.4 source"
    (doc_dir / "stored.pdf").write_bytes(payload)

    response = auth_client.get(f"/api/documents/{doc_id}/original")
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "private, no-store"


def test_position_migration_is_idempotent(auth_client):
    doc_id, user_id = _document(auth_client)
    insert_chunks([{"chunk_id": f"{doc_id}:0", "doc_id": doc_id, "text": "one"}], user_id)
    init_chunk_tables()
    init_chunk_tables()
    response = auth_client.get(f"/api/documents/{doc_id}/source")
    assert response.json()["chunks"][0]["position"] == 0
