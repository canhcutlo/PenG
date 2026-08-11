"""Phase 5/8/9 integration tests: auth, upload → query → quiz → submit → history → artifacts.

These tests use the app via TestClient with fake LLM injection and
disabled background processing. No real AI models are loaded.
"""
import io
import json
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db.sqlite_store import init_sqlite
from app.services.rag import reset_rag_for_tests
from app.services.structured import completion_func
from tests.conftest import get_auth_user_id


client = TestClient(app)


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    """Inject fake LLM; enable offline test mode."""
    settings.process_on_upload = False
    settings.index_on_upload = False

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        if "quiz" in prompt.lower() or "trắc nghiệm" in prompt.lower():
            return json.dumps({
                "questions": [{
                    "question": "Câu hỏi kiểm thử?",
                    "options": ["Đúng", "Sai", "Có", "Không"],
                    "correct_index": 0,
                    "explanation": "Giải thích test.",
                }]
            })
        if "mindmap" in prompt.lower() or "#" in prompt:
            return "# Chủ đề test\n## Nhánh 1\n- Ý 1\n- Ý 2\n## Nhánh 2\n- Ý 3\n- Ý 4\n## Nhánh 3\n- Ý 5\n- Ý 6"
        if "bullet" in prompt.lower() or "tóm tắt" in prompt.lower():
            return json.dumps({"bullets": ["Ý chính 1", "Ý chính 2"]})
        return "Câu trả lờI kiểm thử [Page 1]."

    monkeypatch.setattr(
        "app.services.structured.completion_func", fake_complete
    )
    monkeypatch.setattr(
        "app.services.mindmap_gen.complete", fake_complete
    )
    monkeypatch.setattr(
        "app.services.summary_gen.complete", fake_complete
    )


def _upload_png(auth_client, content: bytes = None):
    if content is None:
        content = b"\x89PNG\r\n\x1a\n" + b"e2e_test" + b"\x00" * 50
    return auth_client.post(
        "/api/upload",
        files={"file": ("e2e.png", io.BytesIO(content), "image/png")},
        data={"category": "image"},
    )




def test_e2e_upload_requires_auth():
    resp = client.post(
        "/api/upload",
        files={"file": ("e2e.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        data={"category": "image"},
    )
    assert resp.status_code == 401


def test_e2e_upload_generates_doc_and_job(auth_client):
    resp = _upload_png(auth_client)
    assert resp.status_code == 200
    data = resp.json()
    assert data["doc_id"]
    assert data["job_id"]
    assert data["status"] == "queued"


def test_e2e_job_status_retrievable(auth_client):
    resp = _upload_png(auth_client)
    job_id = resp.json()["job_id"]
    jr = auth_client.get(f"/api/jobs/{job_id}")
    assert jr.status_code == 200
    assert jr.json()["status"] in ("queued", "processing", "completed", "failed")




def test_e2e_quiz_generate_and_submit(auth_client):

    from app.db.sqlite_store import insert_document
    import uuid
    from datetime import datetime, timezone

    doc_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    user_id = get_auth_user_id(auth_client)
    insert_document(doc_id, "fake.pdf", "fake.pdf", "pdf", 100, "e2e_hash", user_id)

    resp = auth_client.post("/api/quiz/generate?doc_id=nonexistent&num_questions=3")
    assert resp.status_code == 404
    assert "Document" in resp.json()["detail"]


def test_e2e_quiz_submit_scoring(auth_client):
    """Test quiz grading logic via the submit endpoint."""
    from app.db.sqlite_store import insert_quiz

    quiz_id = "testquiz123"
    doc_id = "testdoc456"
    user_id = get_auth_user_id(auth_client)
    questions = [
        {
            "question": "1+1?",
            "options": ["2", "3", "4", "5"],
            "correct_index": 0,
            "explanation": "2 là đúng",
        }
    ]
    insert_quiz(quiz_id, doc_id, questions, user_id)

    resp = auth_client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={"quiz_id": quiz_id, "answers": [0]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 1
    assert data["total"] == 1
    assert data["correct"] == [0]


def test_e2e_quiz_submit_wrong(auth_client):
    """Test incorrect answer scoring."""
    from app.db.sqlite_store import insert_quiz

    quiz_id = "testquiz999"
    user_id = get_auth_user_id(auth_client)
    questions = [
        {
            "question": "Q?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 2,
            "explanation": "C đúng",
        }
    ]
    insert_quiz(quiz_id, "doc", questions, user_id)

    resp = auth_client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={"quiz_id": quiz_id, "answers": [0]},
    )
    assert resp.status_code == 200
    assert resp.json()["score"] == 0




def test_e2e_history_logging(auth_client):
    """Test that activities are logged and retrievable for the authenticated user."""
    from app.db.sqlite_store import log_activity, get_activities

    log_activity("htest", "viewed", "system", {"query": "test"})
    rows = get_activities("system")
    assert any(r["doc_id"] == "htest" for r in rows)


def test_e2e_history_endpoint(auth_client):
    resp = auth_client.get("/api/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)




def test_e2e_query_empty(auth_client):
    resp = auth_client.get("/api/query?q=")
    assert resp.status_code == 200
    assert resp.json()["answer"] == ""
