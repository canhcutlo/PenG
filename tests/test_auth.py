"""Auth tests: register, login, logout, me, CSRF, ownership isolation."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.auth import create_test_user, create_test_session
from app.db.auth_store import hash_token, SYSTEM_USER_ID
from app.db.sqlite_store import insert_document, get_document




def _fresh_client() -> TestClient:
    return TestClient(app)


def test_register_success():
    c = _fresh_client()
    resp = c.post(
        "/api/auth/register",
        json={"username": "newuser_abc", "password": "securepass123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser_abc"
    assert "user_id" in data


def test_register_duplicate():
    c = _fresh_client()
    username = "dupuser_xyz"
    c.post("/api/auth/register", json={"username": username, "password": "securepass123"})
    resp = c.post("/api/auth/register", json={"username": username, "password": "securepass123"})
    assert resp.status_code == 409


def test_register_weak_password():
    c = _fresh_client()
    resp = c.post("/api/auth/register", json={"username": "weakuser", "password": "123"})
    assert resp.status_code == 400


def test_login_success():
    c = _fresh_client()
    username = "loginuser_1"
    password = "securepass123"
    c.post("/api/auth/register", json={"username": username, "password": password})

    resp = c.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    assert resp.cookies.get("peng_session")
    assert resp.cookies.get("peng_csrf")


def test_login_wrong_password():
    c = _fresh_client()
    username = "loginuser_2"
    c.post("/api/auth/register", json={"username": username, "password": "securepass123"})
    resp = c.post("/api/auth/login", json={"username": username, "password": "wrongpass"})
    assert resp.status_code == 401


def test_me_requires_auth():
    c = _fresh_client()
    resp = c.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_user():
    c = _fresh_client()
    username = "meuser_1"
    password = "securepass123"
    c.post("/api/auth/register", json={"username": username, "password": password})
    login_resp = c.post("/api/auth/login", json={"username": username, "password": password})
    csrf = login_resp.cookies.get("peng_csrf")

    c.headers["X-CSRF-Token"] = csrf

    resp = c.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == username


def test_logout_clears_cookies():
    c = _fresh_client()
    username = "logoutuser_1"
    password = "securepass123"
    c.post("/api/auth/register", json={"username": username, "password": password})
    login_resp = c.post("/api/auth/login", json={"username": username, "password": password})
    csrf = login_resp.cookies.get("peng_csrf")

    c.headers["X-CSRF-Token"] = csrf

    resp = c.post("/api/auth/logout")
    assert resp.status_code == 204
    me_resp = c.get("/api/auth/me")
    assert me_resp.status_code == 401


def test_csrf_required_for_logout():
    c = _fresh_client()
    username = "csrfuser_1"
    password = "securepass123"
    c.post("/api/auth/register", json={"username": username, "password": password})
    login_resp = c.post("/api/auth/login", json={"username": username, "password": password})

    c2 = _fresh_client()
    c2.cookies.update(login_resp.cookies)
    resp = c2.post("/api/auth/logout")
    assert resp.status_code == 403


def test_upload_ownership_isolation():
    """User A must not see User B's document."""
    import io
    import uuid

    user_a = {"username": f"usera_{uuid.uuid4().hex[:6]}", "password": "securepass123"}
    user_b = {"username": f"userb_{uuid.uuid4().hex[:6]}", "password": "securepass123"}

    ca = _fresh_client()
    ca.post("/api/auth/register", json=user_a)
    r = ca.post("/api/auth/login", json=user_a)
    ca.cookies.update(r.cookies)
    ca.headers["X-CSRF-Token"] = r.cookies.get("peng_csrf")

    cb = _fresh_client()
    cb.post("/api/auth/register", json=user_b)
    r = cb.post("/api/auth/login", json=user_b)
    cb.cookies.update(r.cookies)
    cb.headers["X-CSRF-Token"] = r.cookies.get("peng_csrf")

    content = b"\x89PNG\r\n\x1a\n" + b"isolation" + b"\x00" * 50
    upload_resp = ca.post(
        "/api/upload",
        files={"file": ("iso.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )
    doc_id = upload_resp.json()["doc_id"]

    resp_b = cb.get(f"/api/mindmap/{doc_id}")
    assert resp_b.status_code == 404


def test_document_ownership_service():
    """Direct DB ownership check via get_document."""
    user = create_test_user("own_test_user", "testpass123")
    doc_id = "owned_doc_001"
    insert_document(doc_id, "f.pdf", "f.pdf", "pdf", 10, "hash1", user["user_id"])

    assert get_document(doc_id, user["user_id"]) is not None
    assert get_document(doc_id, "system") is None


def test_session_hash_not_plaintext():
    token = create_test_session(SYSTEM_USER_ID)
    assert hash_token(token) != token
