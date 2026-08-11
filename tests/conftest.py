"""Pytest fixtures for PenG — DB initialization, cleanup, and auth bootstrap."""
import pytest
import shutil
from app.db.sqlite_store import init_sqlite
from app.db.auth_store import ensure_system_user
from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Ensure SQLite tables exist once per test session; disable background processing."""
    settings.process_on_upload = False
    settings.index_on_upload = False
    settings.llm_device = "cpu"
    settings.auth_cookie_secure = False

    db_path = settings.sqlite_path
    if db_path.exists():
        db_path.unlink()
    if settings.upload_dir.exists():
        shutil.rmtree(settings.upload_dir)
    if settings.lightrag_working_dir.exists():
        shutil.rmtree(settings.lightrag_working_dir)
    settings.upload_dir.mkdir(exist_ok=True)
    init_sqlite()
    yield


@pytest.fixture
def test_user():
    """Return a freshly created test user."""
    from app.services.auth import create_test_user
    return create_test_user()


@pytest.fixture
def auth_client():
    """Return a TestClient logged in as a unique user, with CSRF header support."""
    import uuid
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    username = f"testuser_{uuid.uuid4().hex[:8]}"

    resp = client.post(
        "/api/auth/register",
        json={"username": username, "password": "testpass123"},
    )
    assert resp.status_code == 201

    resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": "testpass123"},
    )
    assert resp.status_code == 200

    csrf_token = client.cookies.get("peng_csrf")
    assert csrf_token

    client.headers["X-CSRF-Token"] = csrf_token
    client._test_username = username
    return client


def get_auth_user_id(client) -> str:
    """Return the user_id of a logged-in TestClient."""
    from app.db.auth_store import get_session_by_hash, hash_token
    token = client.cookies.get("peng_session")
    session = get_session_by_hash(hash_token(token))
    return session["user_id"]
