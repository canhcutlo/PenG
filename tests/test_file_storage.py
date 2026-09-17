# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Focused tests for safe, streaming upload storage."""
import hashlib
import io

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.config import settings
import app.services.file_storage as file_storage
from app.services.file_storage import (
    UPLOAD_CHUNK_SIZE,
    cleanup_document,
    save_upload,
    validate_upload,
)


class RecordingBytesIO(io.BytesIO):
    """BytesIO that records requested read sizes for the streaming assertion."""

    def __init__(self, content: bytes):
        super().__init__(content)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        return super().read(size)


def make_upload(filename: str, content_type: str, content: bytes = b"content") -> UploadFile:
    return UploadFile(
        filename=filename,
        file=io.BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


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
async def test_save_upload_reads_bounded_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_size_mb", 3)
    source = RecordingBytesIO(b"x" * (UPLOAD_CHUNK_SIZE + 17))
    upload = UploadFile(filename="large.pdf", file=source)

    _, size, _ = await save_upload(upload, "chunked-doc")

    assert size == UPLOAD_CHUNK_SIZE + 17
    assert source.read_sizes
    assert set(source.read_sizes) == {UPLOAD_CHUNK_SIZE}


@pytest.mark.asyncio
async def test_save_upload_removes_partial_file_when_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    upload = UploadFile(filename="too-large.png", file=io.BytesIO(b"not-empty"))

    with pytest.raises(HTTPException) as exc_info:
        await save_upload(upload, "oversized-doc")

    assert exc_info.value.status_code == 413
    assert not (tmp_path / "oversized-doc").exists()


@pytest.mark.asyncio
async def test_save_upload_removes_partial_file_when_finalizing_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    upload = UploadFile(filename="lesson.pdf", file=io.BytesIO(b"partial content"))

    def fail_replace(source, destination):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(file_storage.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated disk failure"):
        await save_upload(upload, "failed-doc")

    assert not (tmp_path / "failed-doc").exists()


@pytest.mark.asyncio
async def test_cleanup_document_removes_duplicate_upload(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    upload = UploadFile(filename="duplicate.png", file=io.BytesIO(b"same content"))

    await save_upload(upload, "duplicate-doc")
    cleanup_document("duplicate-doc")

    assert not (tmp_path / "duplicate-doc").exists()


def test_validate_upload_accepts_configured_webm():
    upload = make_upload("lesson.webm", "video/webm")

    validate_upload(upload, "video")


def test_validate_upload_rejects_legacy_doc():
    upload = make_upload("lesson.doc", "application/msword")

    with pytest.raises(HTTPException) as exc_info:
        validate_upload(upload, "pdf")

    assert exc_info.value.status_code == 400


def test_validate_upload_uses_settings_as_source_of_truth(monkeypatch):
    monkeypatch.setattr(settings, "allowed_video_extensions", ".mp4")
    upload = make_upload("lesson.webm", "video/webm")

    with pytest.raises(HTTPException) as exc_info:
        validate_upload(upload, "video")

    assert exc_info.value.status_code == 400
