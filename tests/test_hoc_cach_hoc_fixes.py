# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Verification tests for Mindmap, Quiz, and Chat fixes using hoc-cach-hoc.md.

Can be run with pytest or directly via `python tests/test_hoc_cach_hoc_fixes.py`.
"""
import asyncio
import json
from pathlib import Path
import pytest

from app.models.schemas import FaithfulAnswer
from app.services import structured
from app.services.faithfulness import (
    EvidenceItem,
    _is_explanatory_question,
    _is_answer_truncated,
    generate_faithful_answer,
)
from app.services.mindmap_gen import (
    build_fallback_mindmap,
    validate_mindmap_structure,
)
from app.services.prompts import (
    FAITHFUL_CHAT_PROMPT,
    build_faithful_chat_prompt,
)
from app.services.quiz_gen import (
    QuizItem,
    QuizOutput,
    generate_quiz,
)
from app.services.structured import GenerationError, _format_validation_error


def load_hoc_cach_hoc_text() -> str:
    path = Path(__file__).resolve().parents[1] / "uploads" / "b63bb6ca982a" / "hoc-cach-hoc.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return (
        "# Học Cách Học: Kỹ Năng Quan Trọng\n\n"
        "## 1. Bản chất việc học\nNão bộ ghi nhớ thông tin qua liên kết thần kinh.\n"
        "## 2. Phương pháp hiệu quả\nActive Recall và Spaced Repetition là chìa khóa.\n"
        "## 3. Kỹ thuật Feynman\nGiải thích khái niệm đơn giản như dạy cho trẻ 12 tuổi.\n"
    )


def test_mindmap_hoc_cach_hoc_fallback_and_validation():
    """Test Mindmap generation and validation on hoc-cach-hoc.md content."""
    text = load_hoc_cach_hoc_text()

    # 1. Fallback mindmap extraction
    fallback_md = build_fallback_mindmap(text)
    assert fallback_md.startswith("# ")
    assert "## " in fallback_md

    # 2. Crucial: NO fake dummy sentences
    assert "Thông tin chính của" not in fallback_md, "Dummy placeholder found in fallback mindmap!"

    # 3. Structure validation must pass on the extracted fallback
    assert validate_mindmap_structure(fallback_md) is True

    # 4. Realistic LLM markdown with H1, H2, H3, and bullets must also pass
    llm_md = (
        "# Học Cách Học\n"
        "## Nguyên lý khoa học\n"
        "### Hai chế độ tư duy\n"
        "- Chế độ tập trung (focused mode)\n"
        "- Chế độ khuếch tán (diffuse mode)\n"
        "### Trí nhớ làm việc và dài hạn\n"
        "- Trí nhớ làm việc giới hạn dung lượng\n"
        "- Trí nhớ dài hạn lưu trữ bền vững\n"
        "## Phương pháp học tập\n"
        "- Active Recall: chủ động truy xuất thông tin\n"
        "- Spaced Repetition: lặp lại ngắt quãng\n"
        "- Feynman: giải thích bằng ngôn ngữ đơn giản\n"
        "## Xây dựng hệ thống bền vững\n"
        "- Quản lý sự chú ý thay vì chỉ thời gian\n"
        "- Giữ gìn giấc ngủ và thể lực\n"
    )
    assert validate_mindmap_structure(llm_md) is True, "validate_mindmap_structure should accept H1, H2, H3, and bullets"


@pytest.mark.asyncio
async def test_quiz_hoc_cach_hoc_generation(monkeypatch):
    """Test Quiz generation parameters (temperature=0.35, max_new_tokens, error hints)."""
    text = load_hoc_cach_hoc_text()
    captured_kwargs = {}

    quiz_payload = json.dumps({
        "questions": [
            {
                "question": "Hai chế độ tư duy của não bộ là gì?",
                "options": ["Tập trung và Khuếch tán", "Chủ động và Bị động", "Ghi nhớ và Lãng quên", "Nhanh và Chậm"],
                "correct_index": 0,
                "explanation": "Não bộ luân phiên giữa chế độ tập trung và chế độ khuếch tán.",
            },
            {
                "question": "Phương pháp Active Recall yêu cầu người học làm gì?",
                "options": ["Đọc lại nhiều lần", "Chủ động nhớ lại không nhìn sách", "Nghe podcast thụ động", "Học nhồi nhét"],
                "correct_index": 1,
                "explanation": "Active Recall buộc người học chủ động truy xuất thông tin từ trí nhớ.",
            },
            {
                "question": "Kỹ thuật Feynman gồm bao nhiêu bước chính?",
                "options": ["2 bước", "3 bước", "4 bước", "5 bước"],
                "correct_index": 2,
                "explanation": "Kỹ thuật Feynman gồm 4 bước đơn giản hóa và lấp lỗ hổng kiến thức.",
            },
        ]
    })

    async def fake_completion(prompt, system_prompt=None, **kwargs):
        captured_kwargs.update(kwargs)
        return quiz_payload

    monkeypatch.setattr(structured, "completion_func", fake_completion)

    quiz = await generate_quiz(text, num_questions=3)
    assert len(quiz.questions) == 3
    assert captured_kwargs.get("temperature") == 0.35
    # Token budget: min(1536, max(640, 3 * 220)) = 660
    assert captured_kwargs.get("max_new_tokens") == 660

    # Test duplicate options error hint
    duplicate_payload = json.dumps({
        "questions": [
            {
                "question": "Phương pháp nào hiệu quả?",
                "options": ["Active Recall", "Active Recall", "Đọc lại", "Nhồi nhét"],
                "correct_index": 0,
                "explanation": "Trùng lặp đáp án.",
            }
        ]
    })

    calls = {"n": 0, "hints": []}

    async def fake_retry(prompt, system_prompt=None, **kwargs):
        calls["n"] += 1
        if "Fix this validation error:" in prompt:
            calls["hints"].append(prompt.split("Fix this validation error:")[-1])
        if calls["n"] == 1:
            return duplicate_payload
        # Success on attempt 2
        return json.dumps({
            "questions": [
                {
                    "question": "Phương pháp nào hiệu quả?",
                    "options": ["Active Recall", "Spaced Repetition", "Đọc lại", "Nhồi nhét"],
                    "correct_index": 0,
                    "explanation": "Các phương pháp chủ động hiệu quả nhất.",
                }
            ]
        })

    monkeypatch.setattr(structured, "completion_func", fake_retry)
    result = await generate_quiz(text, num_questions=1)
    assert len(result.questions) == 1
    assert calls["n"] == 2
    assert len(calls["hints"]) == 1
    assert "Ensure all 4 options in each question are completely distinct and unique." in calls["hints"][0]


@pytest.mark.asyncio
async def test_chat_hoc_cach_hoc_faithfulness(monkeypatch):
    """Test Chat faithfulness: prompt schema reminder, explanatory token budget, and truncation guard."""
    # 1. Verify schema reminder in FAITHFUL_CHAT_PROMPT
    rendered_prompt = build_faithful_chat_prompt(
        question="Giải thích các nội dung quan trọng",
        context="[E1]\nNội dung bài học",
        history="",
        output_language="vi",
    )
    assert 'Respond with JSON matching this schema:' in rendered_prompt
    assert '"answer": "your concise answer in vi (Tiếng Việt)"' in rendered_prompt

    # 2. Verify explanatory question keyword detection
    assert _is_explanatory_question("Giải thích nội dung quan trọng nhất của bài học") is True
    assert _is_explanatory_question("Tổng quan phương pháp Feynman") is True
    assert _is_explanatory_question("Ai là tác giả?") is False

    # 3. Verify truncation detection
    assert _is_answer_truncated("Phương pháp học bao gồm Active Recall và") is True
    assert _is_answer_truncated("Học cách học giúp nâng cao hiệu quả,") is True
    assert _is_answer_truncated("Học cách học giúp nâng cao hiệu quả.") is False

    # 4. Verify token budget and execution
    evidence = [
        EvidenceItem(
            id="E1",
            doc_id="hoc-cach-hoc",
            chunk_id="c1",
            text="Học cách học là kỹ năng nền tảng quan trọng nhất của thế kỷ 21.",
            page=1,
            scene=None,
            timestamp=None,
        ),
        EvidenceItem(
            id="E2",
            doc_id="hoc-cach-hoc",
            chunk_id="c2",
            text="Active Recall và Spaced Repetition là hai phương pháp đã được khoa học chứng minh.",
            page=2,
            scene=None,
            timestamp=None,
        ),
    ]

    captured_tokens = {}

    chat_payload = json.dumps({
        "answer": "Nội dung quan trọng nhất là việc học cách học với hai phương pháp Active Recall và Spaced Repetition.",
        "polarity": "yes",
        "evidence_ids": ["E1", "E2"],
        "warnings": [],
    })

    async def fake_chat_completion(prompt, system_prompt=None, **kwargs):
        captured_tokens["max_new_tokens"] = kwargs.get("max_new_tokens")
        return chat_payload

    monkeypatch.setattr(structured, "completion_func", fake_chat_completion)

    # Explanatory question -> should allocate 768 tokens
    ans = await generate_faithful_answer(
        question="Giải thích các nội dung quan trọng nhất trong bài học",
        evidence=evidence,
        is_chat=True,
    )
    assert ans.polarity == "yes"
    assert "E1" in ans.evidence_ids
    assert captured_tokens.get("max_new_tokens") == 768

    # Specific question -> should allocate 512 tokens
    ans_specific = await generate_faithful_answer(
        question="Phương pháp nào được chứng minh?",
        evidence=evidence,
        is_chat=True,
    )
    assert captured_tokens.get("max_new_tokens") == 512


async def _run_all():
    print("=== Running Mindmap Tests ===")
    test_mindmap_hoc_cach_hoc_fallback_and_validation()
    print("-> Mindmap: PASS")

    print("\n=== Running Quiz Tests ===")
    class MonkeyPatchMock:
        def setattr(self, obj, attr, val):
            setattr(obj, attr, val)
    mp = MonkeyPatchMock()
    await test_quiz_hoc_cach_hoc_generation(mp)
    print("-> Quiz: PASS")

    print("\n=== Running Chat Tests ===")
    await test_chat_hoc_cach_hoc_faithfulness(mp)
    print("-> Chat: PASS")

    print("\n>>> ALL VERIFICATION TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    asyncio.run(_run_all())
