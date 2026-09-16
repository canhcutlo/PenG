# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Focused tests for safe, streaming upload storage."""
import hashlib
import io

import pytest
from fastapi import HTTPException, UploadFile

from app.config import settings
from app.services.file_storage import save_upload


@pytest.mark.asyncio
async def test_save_upload_returns_streamed_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_size_mb", 3)
    content = (b"PenG upload chunk" * 200_000)[:2_500_000]
    upload = UploadFile(filename="lesson.webm", file=io.BytesIO(content))

    path, size, checksum = await save_upload(upload, "streamed-doc")

    assert path.read_bytes() == content
    assert size == len(content)
    assert checksum == hashlib.sha256(content).hexdigest()
    assert not list(path.parent.glob("*.part"))


@pytest.mark.asyncio
async def test_save_upload_removes_partial_file_when_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    upload = UploadFile(filename="too-large.png", file=io.BytesIO(b"not-empty"))

    with pytest.raises(HTTPException) as exc_info:
        await save_upload(upload, "oversized-doc")

    assert exc_info.value.status_code == 413
    assert not (tmp_path / "oversized-doc").exists()
