# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Pytest fixtures for PenG — DB initialization, cleanup, and auth bootstrap."""
import pytest
import shutil
from app.db.sqlite_store import init_sqlite
from app.db.auth_store import ensure_system_user
from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_db(tmp_path_factory):
    """Ensure SQLite tables exist once per test session; disable background processing."""
    settings.process_on_upload = False
    settings.index_on_upload = False
    settings.llm_device = "cpu"
    settings.auth_cookie_secure = False

    test_dir = tmp_path_factory.mktemp("peng_test")
    orig_sqlite = settings.sqlite_path
    orig_upload = settings.upload_dir
    orig_lightrag = settings.lightrag_working_dir

    settings.sqlite_path = test_dir / "test_peng_history.db"
    settings.upload_dir = test_dir / "test_uploads"
    settings.lightrag_working_dir = test_dir / "test_lightrag"

    settings.upload_dir.mkdir(exist_ok=True)
    init_sqlite()
    yield

    settings.sqlite_path = orig_sqlite
    settings.upload_dir = orig_upload
    settings.lightrag_working_dir = orig_lightrag


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
