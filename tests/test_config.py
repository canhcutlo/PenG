"""Tests for configuration and project-root path resolution."""
import os
from pathlib import Path

import pytest

from app.config import PROJECT_ROOT, Settings, settings


def test_project_root_is_absolute_and_named():
    assert PROJECT_ROOT.is_absolute()
    assert PROJECT_ROOT.name == "PenG"
    assert (PROJECT_ROOT / "app" / "config.py").exists()


def test_default_settings_paths_are_absolute():
    assert settings.upload_dir.is_absolute()
    assert settings.sqlite_path.is_absolute()
    assert settings.lightrag_working_dir.is_absolute()


def test_default_settings_paths_resolve_under_project_root():
    assert settings.upload_dir == PROJECT_ROOT / "uploads"
    assert settings.sqlite_path == PROJECT_ROOT / "peng_history.db"
    assert settings.lightrag_working_dir == PROJECT_ROOT / "lightrag_data"


def test_relative_env_paths_resolve_to_project_root(monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", "custom_uploads")
    monkeypatch.setenv("SQLITE_PATH", "custom_peng.db")
    monkeypatch.setenv("LIGHTRAG_WORKING_DIR", "custom_lightrag")

    fresh = Settings()
    assert fresh.upload_dir == PROJECT_ROOT / "custom_uploads"
    assert fresh.sqlite_path == PROJECT_ROOT / "custom_peng.db"
    assert fresh.lightrag_working_dir == PROJECT_ROOT / "custom_lightrag"


def test_absolute_env_paths_are_preserved(monkeypatch, tmp_path):
    abs_upload = tmp_path / "abs_uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(abs_upload))

    fresh = Settings()
    assert fresh.upload_dir == abs_upload


def test_static_dir_in_main_is_absolute():
    from app.main import STATIC_DIR

    assert STATIC_DIR.is_absolute()
    assert STATIC_DIR == PROJECT_ROOT / "static"


def test_no_allowed_mime_types_setting():
    assert not hasattr(settings, "allowed_mime_types")
