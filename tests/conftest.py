"""Pytest fixtures for PenG — DB initialization and cleanup."""
import pytest
import shutil
from app.db.sqlite_store import init_sqlite
from app.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Ensure SQLite tables exist once per test session; disable background processing."""
    settings.process_on_upload = False
    settings.index_on_upload = False
    settings.llm_device = "cpu"

    db_path = settings.sqlite_path
    if db_path.exists():
        db_path.unlink()
    if settings.upload_dir.exists():
        shutil.rmtree(settings.upload_dir)
    settings.upload_dir.mkdir(exist_ok=True)
    init_sqlite()
    yield
