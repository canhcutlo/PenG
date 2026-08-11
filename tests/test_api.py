"""API tests for PenG backend."""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)




def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"




def test_upload_requires_auth():
    """Upload without auth should return 401."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    response = client.post(
        "/api/upload",
        files={"file": ("test.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    assert response.status_code == 401


def test_upload_valid_image(auth_client):
    """Upload a valid PNG file — expect 200 with doc_id + job_id."""
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    response = auth_client.post(
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


def test_upload_valid_audio(auth_client):
    """Upload a valid MP3 file."""
    content = b"\xff\xfb\x90\x00" + b"\x00" * 200
    response = auth_client.post(
        "/api/upload",
        files={"file": ("test.mp3", io.BytesIO(content), "audio/mpeg")},
        data={"category": "audio"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "audio"


def test_upload_valid_pdf(auth_client):
    """Upload a valid PDF."""
    content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n" + b"x" * 100
    response = auth_client.post(
        "/api/upload",
        files={"file": ("test.pdf", io.BytesIO(content), "application/pdf")},
        data={"category": "pdf"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "pdf"


def test_upload_invalid_extension(auth_client):
    """Upload .exe — expect 400."""
    content = b"MZ\x90\x00" + b"\x00" * 100
    response = auth_client.post(
        "/api/upload",
        files={"file": ("malware.exe", io.BytesIO(content), "application/x-msdownload")},
        data={"category": "image"},
    )
    assert response.status_code == 400


def test_upload_invalid_category(auth_client):
    """Upload with unknown category — expect 400."""
    content = b"hello"
    response = auth_client.post(
        "/api/upload",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        data={"category": "document"},
    )
    assert response.status_code == 400


def test_upload_no_file(auth_client):
    """POST without file — expect 422."""
    response = auth_client.post("/api/upload")
    assert response.status_code == 422


def test_upload_duplicate(auth_client):
    """Upload same content twice — second should return existing doc_id."""
    content = b"\x89PNG\r\n\x1a\n" + b"dup_test" + b"\x00" * 50
    resp1 = auth_client.post(
        "/api/upload",
        files={"file": ("dup.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    assert resp1.status_code == 200
    doc_id_1 = resp1.json()["doc_id"]

    resp2 = auth_client.post(
        "/api/upload",
        files={"file": ("dup2.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["doc_id"] == doc_id_1




def test_get_job_requires_auth():
    response = client.get("/api/jobs/abc123")
    assert response.status_code == 401


def test_get_job_valid(auth_client):
    """Upload then fetch job status — expect 200 with status."""
    content = b"\x89PNG\r\n\x1a\n" + b"job_test" + b"\x00" * 50
    upload_resp = auth_client.post(
        "/api/upload",
        files={"file": ("job.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    job_id = upload_resp.json()["job_id"]

    response = auth_client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["status"] == "queued"
    assert data["progress"] == 0


def test_get_job_not_found(auth_client):
    """Fetch non-existent job — expect 404."""
    response = auth_client.get("/api/jobs/nonexistent123")
    assert response.status_code == 404




def test_query_requires_auth():
    response = client.get("/api/query?q=hello")
    assert response.status_code == 401


def test_query_empty(auth_client):
    response = auth_client.get("/api/query?q=&top_k=3")
    assert response.status_code == 200
