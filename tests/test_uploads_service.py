# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Tests for upload orchestration after the router/service split."""
import io

import pytest
from fastapi import UploadFile

from app.config import settings
import app.services.uploads as uploads


@pytest.mark.asyncio
async def test_create_upload_uses_streamed_size_and_checksum(tmp_path, monkeypatch):
    saved_path = tmp_path / "new-doc" / "lesson.pdf"
    saved_path.parent.mkdir()
    captured = {}

    async def fake_save_upload(file, doc_id):
        return saved_path, 1234, "streamed-checksum"

    def fake_insert_document(doc_id, filename, original_name, category, size, checksum, user_id):
        captured.update(size=size, checksum=checksum)
        return {
            "doc_id": doc_id,
            "filename": filename,
            "original_name": original_name,
            "category": category,
            "status": "queued",
        }

    monkeypatch.setattr(uploads, "save_upload", fake_save_upload)
    monkeypatch.setattr(uploads, "find_document_by_checksum", lambda checksum, user_id: None)
    monkeypatch.setattr(uploads, "insert_document", fake_insert_document)
    monkeypatch.setattr(
        uploads,
        "insert_job",
        lambda job_id, doc_id, job_type, user_id: {"job_id": job_id},
    )
    monkeypatch.setattr(settings, "process_on_upload", False)
    upload = UploadFile(filename="lesson.pdf", file=io.BytesIO(b"content"))

    response, task = await uploads.create_upload(upload, "pdf", "user-1")

    assert response.filename == "lesson.pdf"
    assert captured == {"size": 1234, "checksum": "streamed-checksum"}
    assert task is None


@pytest.mark.asyncio
async def test_create_upload_cleans_duplicate_and_returns_existing_document(tmp_path, monkeypatch):
    saved_path = tmp_path / "new-doc" / "duplicate.png"
    saved_path.parent.mkdir()
    cleaned = []
    existing = {
        "doc_id": "existing-doc",
        "filename": "original.png",
        "original_name": "original.png",
        "category": "image",
        "status": "completed",
    }

    async def fake_save_upload(file, doc_id):
        return saved_path, 12, "duplicate-checksum"

    monkeypatch.setattr(uploads, "save_upload", fake_save_upload)
    monkeypatch.setattr(
        uploads,
        "find_document_by_checksum",
        lambda checksum, user_id: existing,
    )
    monkeypatch.setattr(uploads, "cleanup_document", cleaned.append)
    monkeypatch.setattr(
        uploads,
        "insert_job",
        lambda job_id, doc_id, job_type, user_id: {"job_id": job_id},
    )
    monkeypatch.setattr(settings, "process_on_upload", True)
    upload = UploadFile(filename="duplicate.png", file=io.BytesIO(b"same content"))

    response, task = await uploads.create_upload(upload, "image", "user-1")

    assert len(cleaned) == 1
    assert response.doc_id == "existing-doc"
    assert task is not None
    assert task[0] == "existing-doc"
    assert task[2] == "user-1"
