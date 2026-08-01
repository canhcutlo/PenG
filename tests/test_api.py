"""API tests for PenG backend."""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


# ─── Health ────────────────────────────────────────────────────────────────


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


# ─── Upload ────────────────────────────────────────────────────────────────


def test_upload_valid_image():
    """Upload a valid PNG file — expect 200 with doc_id + job_id."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header
    response = client.post(
        "/api/upload",
        files={"file": ("test.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "doc_id" in data
    assert "job_id" in data
    assert data["category"] == "image"
    assert data["status"] == "queued"


def test_upload_valid_audio():
    """Upload a valid MP3 file."""
    # Minimal MP3 frame header (sync word + basic header)
    content = b"\xff\xfb\x90\x00" + b"\x00" * 200
    response = client.post(
        "/api/upload",
        files={"file": ("test.mp3", io.BytesIO(content), "audio/mpeg")},
        data={"category": "audio"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "audio"


def test_upload_valid_pdf():
    """Upload a valid PDF."""
    content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"x" * 100
    response = client.post(
        "/api/upload",
        files={"file": ("test.pdf", io.BytesIO(content), "application/pdf")},
        data={"category": "pdf"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "pdf"


def test_upload_invalid_extension():
    """Upload .exe — expect 400."""
    content = b"MZ\x90\x00" + b"\x00" * 100
    response = client.post(
        "/api/upload",
        files={"file": ("malware.exe", io.BytesIO(content), "application/x-msdownload")},
        data={"category": "image"},
    )
    assert response.status_code == 400


def test_upload_invalid_category():
    """Upload with unknown category — expect 400."""
    content = b"hello"
    response = client.post(
        "/api/upload",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        data={"category": "document"},
    )
    assert response.status_code == 400


def test_upload_no_file():
    """POST without file — expect 422."""
    response = client.post("/api/upload")
    assert response.status_code == 422


def test_upload_duplicate():
    """Upload same content twice — second should return existing doc_id."""
    content = b"\x89PNG\r\n\x1a\n" + b"dup_test" + b"\x00" * 50
    resp1 = client.post(
        "/api/upload",
        files={"file": ("dup.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    assert resp1.status_code == 200
    doc_id_1 = resp1.json()["doc_id"]

    resp2 = client.post(
        "/api/upload",
        files={"file": ("dup2.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["doc_id"] == doc_id_1  # same checksum → same doc_id


# ─── Job status ────────────────────────────────────────────────────────────


def test_get_job_valid():
    """Upload then fetch job status — expect 200 with status."""
    content = b"\x89PNG\r\n\x1a\n" + b"job_test" + b"\x00" * 50
    upload_resp = client.post(
        "/api/upload",
        files={"file": ("job.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    job_id = upload_resp.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert data["progress"] == 0


def test_get_job_not_found():
    """Fetch non-existent job — expect 404."""
    response = client.get("/api/jobs/nonexistent123")
    assert response.status_code == 404


# ─── Query (stub — được giữ để kiểm tra route tồn tại) ─────────────────────


def test_query_empty():
    response = client.get("/api/query?q=&top_k=3")
    assert response.status_code == 200
