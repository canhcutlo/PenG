# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Tests for quiz discovery and attempt history endpoints."""
import json
import uuid

from fastapi.testclient import TestClient
from app.db.sqlite_store import insert_document, insert_quiz, insert_quiz_result
from app.main import app
from tests.conftest import get_auth_user_id


def _question() -> dict:
    return {
        "id": 0,
        "question": "Q?",
        "options": ["A", "B", "C", "D"],
        "correct_index": 0,
        "explanation": "A",
    }


def test_quiz_discovery_returns_empty_without_aggregate_join(auth_client, monkeypatch):
    user_id = get_auth_user_id(auth_client)
    doc_id = uuid.uuid4().hex[:12]
    insert_document(doc_id, "empty.pdf", "empty.pdf", "pdf", 10, uuid.uuid4().hex, user_id)

    def fail_list(*_args, **_kwargs):
        raise AssertionError("empty discovery should not run quiz aggregate query")

    monkeypatch.setattr("app.routers.quiz.list_quizzes_for_document", fail_list)
    response = auth_client.get(f"/api/documents/{doc_id}/quizzes")
    assert response.status_code == 200
    assert response.json()["quizzes"] == []
    assert response.json()["total"] == 0


def test_quiz_discovery_stats_and_attempt_pagination(auth_client):
    user_id = get_auth_user_id(auth_client)
    doc_id = uuid.uuid4().hex[:12]
    quiz_id = uuid.uuid4().hex[:12]
    insert_document(doc_id, "f.pdf", "f.pdf", "pdf", 10, uuid.uuid4().hex, user_id)
    insert_quiz(quiz_id, doc_id, [_question()], user_id)
    insert_quiz_result(quiz_id, json.dumps([1]), 0, user_id)
    insert_quiz_result(quiz_id, json.dumps([0]), 1, user_id)

    response = auth_client.get(f"/api/documents/{doc_id}/quizzes?limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    summary = data["quizzes"][0]
    assert summary["question_count"] == 1
    assert summary["attempt_count"] == 2
    assert summary["best_score"] == 1
    assert summary["latest_score"] == 1

    response = auth_client.get(f"/api/quiz/{quiz_id}/attempts?limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["attempts"][0]["answers"] == [0]
    assert data["attempts"][0]["total"] == 1


def test_quiz_discovery_ownership_and_old_api(auth_client):
    user_id = get_auth_user_id(auth_client)
    doc_id = uuid.uuid4().hex[:12]
    quiz_id = uuid.uuid4().hex[:12]
    insert_document(doc_id, "f.pdf", "f.pdf", "pdf", 10, uuid.uuid4().hex, user_id)
    insert_quiz(quiz_id, doc_id, [_question()], user_id)

    assert auth_client.get(f"/api/quiz/{quiz_id}").status_code == 200

    other = TestClient(app)
    name = f"quiz_other_{uuid.uuid4().hex[:6]}"
    other.post("/api/auth/register", json={"username": name, "password": "securepass123"})
    other.post("/api/auth/login", json={"username": name, "password": "securepass123"})
    assert other.get(f"/api/documents/{doc_id}/quizzes").status_code == 404
    assert other.get(f"/api/quiz/{quiz_id}/attempts").status_code == 404
    assert other.get(f"/api/quiz/{quiz_id}").status_code == 404
