"""Regression tests for the faithfulness guard.

These tests use fake LLM/embedding functions and avoid downloading models.
"""
import json
import uuid
import pytest

from app.db.artifact_store import get_latest_artifact, insert_artifact
from app.db.chunk_store import insert_chunks
from app.db.sqlite_store import insert_document
from app.models.schemas import FaithfulAnswer
from app.services import structured
from app.services.chat import create_chat_session, post_chat_message
from app.services.faithfulness import (
    EvidenceItem,
    apply_eligibility_guard,
    apply_guard_rules,
    generate_faithful_answer,
    normalize_evidence,
    validate_evidence_ids,
)
from app.services.prompts import detect_question_language
from app.services.rag import query_documents
from tests.conftest import get_auth_user_id
from tests.test_rag import FakeEmbedding


async def _fake_embed(texts):
    return FakeEmbedding(dim=768).encode(texts)


def _make_fake_llm(payloads: list[str]):
    """Return a fake completion that cycles through JSON payloads."""
    calls = {"n": 0}

    async def fake(prompt, system_prompt=None, **kwargs):
        idx = calls["n"]
        calls["n"] += 1
        if idx < len(payloads):
            return payloads[idx]
        return payloads[-1]

    return fake


def _make_doc_chunks(
    user_id: str,
    texts: list[str],
    pages: list[int | None] | None = None,
):
    doc_id = uuid.uuid4().hex[:12]
    insert_document(doc_id, "f.pdf", "f.pdf", "pdf", 100, uuid.uuid4().hex[:16], user_id)
    pages = pages or [None] * len(texts)
    chunks = []
    for i, text in enumerate(texts):
        chunks.append({
            "chunk_id": f"{doc_id}:{i}",
            "doc_id": doc_id,
            "text": text,
            "page": pages[i],
            "scene": None,
            "timestamp": None,
            "metadata": {"category": "pdf"},
        })
    insert_chunks(chunks, user_id)
    return doc_id


def _make_artifact(doc_id: str, user_id: str, artifact_type: str, content: str):
    insert_artifact(
        artifact_id=uuid.uuid4().hex[:12],
        doc_id=doc_id,
        user_id=user_id,
        artifact_type=artifact_type,
        version=1,
        status="completed",
        content=content,
        input_snapshot={"char_count": 2000, "truncated": False, "source_job": "extract"},
        prompt_version="v1",
    )


RESTRICTIVE_EVIDENCE = "Đối tượng tham gia là tất cả sinh viên hiện đang học tại trường."
OUTSIDER_QUESTION = "người ngoài trường cũng có thể tham gia đúng không?"


def test_normalize_evidence_assigns_stable_ids():
    chunks = [{"doc_id": "d1", "chunk_id": "c1", "text": "text one", "page": 1}]
    evidence = normalize_evidence(chunks)
    assert len(evidence) == 1
    assert evidence[0].id == "E1"
    assert evidence[0].doc_id == "d1"
    assert evidence[0].page == 1


def test_validate_evidence_ids_removes_invalid():
    evidence = [
        EvidenceItem(id="E1", doc_id="d1", chunk_id="c1", text="a", page=None, scene=None, timestamp=None),
        EvidenceItem(id="E2", doc_id="d1", chunk_id="c2", text="b", page=None, scene=None, timestamp=None),
    ]
    answer = FaithfulAnswer(answer="yes", polarity="yes", evidence_ids=["E1", "E99"], warnings=[])
    validated, warnings = validate_evidence_ids(answer, evidence)
    assert validated.evidence_ids == ["E1"]
    assert any("not found" in w.lower() for w in warnings)


def test_validate_evidence_ids_downgrades_when_empty():
    evidence = [
        EvidenceItem(id="E1", doc_id="d1", chunk_id="c1", text="a", page=None, scene=None, timestamp=None),
    ]
    answer = FaithfulAnswer(answer="yes", polarity="yes", evidence_ids=["E99"], warnings=[])
    validated, _ = validate_evidence_ids(answer, evidence)
    assert validated.polarity == "unknown"
    assert validated.evidence_ids == []


def test_guard_overrides_reversed_eligibility_claim():
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text=RESTRICTIVE_EVIDENCE,
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    answer = FaithfulAnswer(
        answer="Đúng, người ngoài cũng có thể tham gia.",
        polarity="yes",
        evidence_ids=["E1"],
        warnings=[],
    )
    guarded, warnings = apply_guard_rules(answer, evidence, OUTSIDER_QUESTION)
    assert guarded.polarity == "no"
    assert "không có bằng chứng" in guarded.answer.lower()
    assert any("restrictive" in w.lower() for w in warnings)


def test_guard_overrides_affirmative_text_even_without_polarity_yes():
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text=RESTRICTIVE_EVIDENCE,
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    answer = FaithfulAnswer(
        answer="Đúng, họ có thể tham gia.",
        polarity="unknown",
        evidence_ids=["E1"],
        warnings=[],
    )
    guarded, warnings = apply_eligibility_guard(answer, evidence, OUTSIDER_QUESTION)
    assert guarded.polarity == "no"
    assert warnings


def test_guard_overrides_english_reversed_eligibility():
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text="Participation is restricted to students currently enrolled at the university.",
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    answer = FaithfulAnswer(
        answer="Yes, external people can participate.",
        polarity="yes",
        evidence_ids=["E1"],
        warnings=[],
    )
    guarded, warnings = apply_guard_rules(answer, evidence, "Can outsiders participate?")
    assert guarded.polarity == "no"
    assert "document only confirms" in guarded.answer.lower()
    assert any("restrictive" in w.lower() for w in warnings)


def test_guard_allows_supported_positive_answer():
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text="Sinh viên hiện đang học tại trường được tham gia.",
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    answer = FaithfulAnswer(
        answer="Đúng, sinh viên được tham gia.",
        polarity="yes",
        evidence_ids=["E1"],
        warnings=[],
    )
    guarded, warnings = apply_guard_rules(answer, evidence, "sinh viên có được tham gia không?")
    assert guarded.polarity == "yes"
    assert guarded.evidence_ids == ["E1"]
    assert not warnings


@pytest.mark.asyncio
async def test_generate_faithful_answer_no_context_vietnamese():
    result = await generate_faithful_answer("câu hỏi", [], history="")
    assert result.polarity == "unknown"
    assert "không tìm thấy" in result.answer.lower()


@pytest.mark.asyncio
async def test_generate_faithful_answer_no_context_english():
    result = await generate_faithful_answer("question", [], history="")
    assert result.polarity == "unknown"
    assert "not enough evidence" in result.answer.lower()


@pytest.mark.asyncio
async def test_generate_faithful_answer_invalid_id_guard(monkeypatch):
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text="Hà Nội là thủ đô.",
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    payload = json.dumps({"answer": "Đúng", "polarity": "yes", "evidence_ids": ["E99"], "warnings": []})
    monkeypatch.setattr(structured, "completion_func", _make_fake_llm([payload]))
    result = await generate_faithful_answer("thủ đô Việt Nam", evidence)
    assert result.polarity == "unknown"
    assert result.evidence_ids == ["E1"]
    assert any("not found" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_generate_faithful_answer_eligibility_override(monkeypatch):
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text=RESTRICTIVE_EVIDENCE,
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    payload = json.dumps({
        "answer": "Đúng, người ngoài cũng có thể tham gia.",
        "polarity": "yes",
        "evidence_ids": ["E1"],
        "warnings": [],
    })
    monkeypatch.setattr(structured, "completion_func", _make_fake_llm([payload, payload]))
    result = await generate_faithful_answer(OUTSIDER_QUESTION, evidence)
    assert result.polarity == "no"
    assert "không có bằng chứng" in result.answer.lower()
    assert result.evidence_ids == ["E1"]


@pytest.mark.asyncio
async def test_generate_faithful_answer_bounded_retry_then_safe(monkeypatch):
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="d1",
            chunk_id="c1",
            text=RESTRICTIVE_EVIDENCE,
            page=1,
            scene=None,
            timestamp=None,
        ),
    ]
    bad = json.dumps({
        "answer": "Đúng, người ngoài có thể.",
        "polarity": "yes",
        "evidence_ids": ["E1"],
        "warnings": [],
    })
    monkeypatch.setattr(structured, "completion_func", _make_fake_llm([bad, bad, bad]))
    result = await generate_faithful_answer(OUTSIDER_QUESTION, evidence, max_retries=1)
    assert result.polarity in ("no", "unknown")
    assert result.warnings


@pytest.mark.asyncio
async def test_chat_path_guard_overrides_wrong_yes(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    monkeypatch.setattr(
        structured,
        "completion_func",
        _make_fake_llm([json.dumps({
            "answer": "Đúng, người ngoài có thể tham gia.",
            "polarity": "yes",
            "evidence_ids": ["E1"],
            "warnings": [],
        })]),
    )

    user_id = get_auth_user_id(auth_client)
    doc_id = _make_doc_chunks(user_id, [RESTRICTIVE_EVIDENCE], pages=[1])
    session = create_chat_session(user_id, doc_id)
    result = await post_chat_message(user_id, session["session_id"], OUTSIDER_QUESTION, "document_and_related")
    assert "không có bằng chứng" in result["answer"].lower()
    assert any("restrictive" in w.lower() for w in result["warnings"])
    assert len(result["citations"]) > 0
    assert result["citations"][0]["doc_id"] == doc_id


@pytest.mark.asyncio
async def test_query_path_uses_real_evidence(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    monkeypatch.setattr(
        structured,
        "completion_func",
        _make_fake_llm([json.dumps({
            "answer": "Hà Nội là thủ đô.",
            "polarity": "yes",
            "evidence_ids": ["E1"],
            "warnings": [],
        })]),
    )
    user_id = get_auth_user_id(auth_client)
    doc_id = _make_doc_chunks(user_id, ["Hà Nội là thủ đô của Việt Nam."], pages=[1])
    result = await query_documents("thủ đô Việt Nam", user_id=user_id, doc_id=doc_id)
    assert "Hà Nội" in result["answer"]
    assert len(result["citations"]) == 1
    assert result["citations"][0]["doc_id"] == doc_id
    assert result["citations"][0]["page"] == 1


@pytest.mark.asyncio
async def test_chat_does_not_modify_artifacts_under_guard(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    monkeypatch.setattr(
        structured,
        "completion_func",
        _make_fake_llm([json.dumps({
            "answer": "Đúng, người ngoài có thể tham gia.",
            "polarity": "yes",
            "evidence_ids": ["E1"],
            "warnings": [],
        })]),
    )
    user_id = get_auth_user_id(auth_client)
    doc_id = _make_doc_chunks(user_id, [RESTRICTIVE_EVIDENCE], pages=[1])
    summary = "- Bullet one\n- Bullet two"
    mindmap = "# Title\n## A\n- a1\n- a2\n## B\n- b1\n- b2\n## C\n- c1\n- c2"
    _make_artifact(doc_id, user_id, "summary", summary)
    _make_artifact(doc_id, user_id, "mindmap", mindmap)

    session = create_chat_session(user_id, doc_id)
    await post_chat_message(user_id, session["session_id"], OUTSIDER_QUESTION, "document_and_related")

    assert get_latest_artifact(doc_id, "summary", status="completed")["content"] == summary
    assert get_latest_artifact(doc_id, "mindmap", status="completed")["content"] == mindmap


def test_detect_question_language_vietnamese():
    assert detect_question_language("Thủ đô của Việt Nam là gì?") == "vi"
    assert detect_question_language("Hà Nội") == "vi"


def test_detect_question_language_english():
    assert detect_question_language("What is the capital of Vietnam?") == "en"
    assert detect_question_language("Hello world") == "en"


@pytest.mark.asyncio
async def test_chat_answers_in_vietnamese_over_english_evidence(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    monkeypatch.setattr(
        structured,
        "completion_func",
        _make_fake_llm([json.dumps({
            "answer": "Đúng, Hà Nội.",
            "polarity": "yes",
            "evidence_ids": ["E1"],
            "warnings": [],
        })]),
    )
    user_id = get_auth_user_id(auth_client)
    doc_id = _make_doc_chunks(user_id, ["Hanoi is the capital of Vietnam."], pages=[1])
    session = create_chat_session(user_id, doc_id)
    result = await post_chat_message(user_id, session["session_id"], "Thủ đô Việt Nam?", "document_and_related")
    assert "Hà Nội" in result["answer"]


@pytest.mark.asyncio
async def test_chat_answers_in_english_over_vietnamese_evidence(auth_client, monkeypatch):
    monkeypatch.setattr("app.services.retrieval.embed", _fake_embed)
    monkeypatch.setattr(
        structured,
        "completion_func",
        _make_fake_llm([json.dumps({
            "answer": "Yes, Hanoi.",
            "polarity": "yes",
            "evidence_ids": ["E1"],
            "warnings": [],
        })]),
    )
    user_id = get_auth_user_id(auth_client)
    doc_id = _make_doc_chunks(user_id, ["Hà Nội là thủ đô của Việt Nam."], pages=[1])
    session = create_chat_session(user_id, doc_id)
    result = await post_chat_message(user_id, session["session_id"], "Capital of Vietnam?", "document_and_related")
    assert "Hanoi" in result["answer"]
