"""Phase 4 tests: structured generation with fake LLM (no real model load)."""
import json
import pytest
from pydantic import BaseModel, Field

from app.services import structured
from app.services.quiz_gen import QuizItem, QuizOutput, generate_quiz
from app.services.mindmap_gen import generate_mindmap_markdown, sanitize_mindmap
from app.services.prompts import build_quiz_prompt, build_mindmap_prompt, build_summary_prompt
from app.services.structured import GenerationError


# ─── Fake LLM helpers ───────────────────────────────────────────────────────


def _make_fake_llm(json_payload: str | None = None, raw_text: str | None = None):
    """Return a fake completion_func that returns the given payload."""

    async def fake(prompt, system_prompt=None, **kwargs):
        if json_payload is not None:
            return json_payload
        return raw_text or "fake response"

    return fake


# ─── Structured generation ──────────────────────────────────────────────────


class MockResult(BaseModel):
    name: str = Field(min_length=2)
    value: int = Field(ge=0)


@pytest.mark.asyncio
async def test_generate_structured_valid_json(monkeypatch):
    monkeypatch.setattr(
        structured,
        "completion_func",
        _make_fake_llm(json_payload=json.dumps({"name": "test", "value": 5})),
    )
    result = await structured.generate_structured(
        "prompt", MockResult, use_instructor=False
    )
    assert result.name == "test"
    assert result.value == 5


@pytest.mark.asyncio
async def test_generate_structured_tolerates_code_fence(monkeypatch):
    payload = '```json\n{"name": "test", "value": 1}\n```'
    monkeypatch.setattr(structured, "completion_func", _make_fake_llm(json_payload=payload))
    result = await structured.generate_structured(
        "prompt", MockResult, use_instructor=False
    )
    assert result.name == "test"


@pytest.mark.asyncio
async def test_generate_structured_retries_on_invalid(monkeypatch):
    """Invalid JSON → retry → eventually valid."""
    calls = {"n": 0}

    async def fake(prompt, system_prompt=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json at all"
        return json.dumps({"name": "ok", "value": 2})

    monkeypatch.setattr(structured, "completion_func", fake)
    result = await structured.generate_structured(
        "prompt", MockResult, use_instructor=False
    )
    assert result.value == 2
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_generate_structured_gives_up_after_retries(monkeypatch):
    async def fake(prompt, system_prompt=None, **kwargs):
        return "invalid forever"

    monkeypatch.setattr(structured, "completion_func", fake)
    with pytest.raises(GenerationError):
        await structured.generate_structured(
            "prompt", MockResult, max_retries=2, use_instructor=False
        )


# ─── Quiz generation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_quiz_valid(monkeypatch):
    quiz_payload = json.dumps(
        {
            "questions": [
                {
                    "question": "Thủ đô Việt Nam?",
                    "options": ["Hà Nội", "Sài Gòn", "Đà Nẵng", "Huế"],
                    "correct_index": 0,
                    "explanation": "Hà Nội là thủ đô.",
                }
            ]
        }
    )
    monkeypatch.setattr(structured, "completion_func", _make_fake_llm(json_payload=quiz_payload))

    result = await generate_quiz("Hà Nội là thủ đô Việt Nam.", num_questions=1)
    assert len(result.questions) == 1
    q = result.questions[0]
    assert len(q.options) == 4
    assert q.correct_index == 0
    assert q.explanation


@pytest.mark.asyncio
async def test_generate_quiz_rejects_duplicate_options(monkeypatch):
    """Pydantic validation rejects duplicated options even if LLM sends them."""
    quiz_payload = json.dumps(
        {
            "questions": [
                {
                    "question": "test",
                    "options": ["A", "A", "B", "C"],
                    "correct_index": 0,
                    "explanation": "x",
                }
            ]
        }
    )
    monkeypatch.setattr(structured, "completion_func", _make_fake_llm(json_payload=quiz_payload))

    with pytest.raises(GenerationError):
        await generate_quiz("text", num_questions=1)


# ─── Mindmap ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_mindmap_sanitizes_html(monkeypatch):
    import app.services.mindmap_gen as mm

    async def fake_complete(prompt, system_prompt=None, **kwargs):
        return "# Chủ đề\n## Nhánh\n<script>alert(1)</script>\n- ý 1"

    monkeypatch.setattr(mm.complete, "__code__", fake_complete.__code__)  # keep sync stub safe
    # Patch the imported function object referenced inside module namespace
    monkeypatch.setattr(mm, "complete", fake_complete)

    result = await generate_mindmap_markdown("nội dung")
    assert "<script>" not in result
    assert result.startswith("# Chủ đề")


@pytest.mark.asyncio
async def test_sanitize_mindmap_limits_depth():
    raw = "# A\n#### B\n- c\n```code```"
    result = sanitize_mindmap(raw)
    assert "####" not in result
    assert "```" not in result


# ─── Prompts ────────────────────────────────────────────────────────────────


def test_build_quiz_prompt_contains_schema():
    p = build_quiz_prompt("text", num_questions=3)
    assert "correct_index" in p
    assert "3" in p


def test_build_mindmap_prompt():
    p = build_mindmap_prompt("text")
    assert "##" in p or "#" in p


def test_build_summary_prompt():
    p = build_summary_prompt("text")
    assert "bullet" in p.lower() or "-" in p
