# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Quiz generation with structured output validation."""
import logging
import re
import uuid
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.prompts import build_quiz_prompt
from app.services.structured import generate_structured, GenerationError

logger = logging.getLogger(__name__)


class QuizItem(BaseModel):
    question: str = Field(min_length=3)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=3)

    @model_validator(mode="before")
    @classmethod
    def normalize_item(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # 1. Normalize correct_index
        idx = data.get("correct_index")
        if isinstance(idx, str):
            idx_clean = idx.strip().upper()
            letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            if idx_clean in letter_map:
                idx = letter_map[idx_clean]
            else:
                try:
                    idx = int(idx_clean)
                except ValueError:
                    idx = 0
        if isinstance(idx, (int, float)):
            idx_int = int(idx)
            # Clamp or adjust 1-based index (e.g. 4 -> 3)
            if idx_int == 4:
                idx_int = 3
            elif idx_int > 3:
                idx_int = 3
            elif idx_int < 0:
                idx_int = 0
            data["correct_index"] = idx_int
        elif idx is None:
            data["correct_index"] = 0

        # 2. Normalize options: ensure exactly 4 elements
        raw_options = data.get("options")
        if isinstance(raw_options, list):
            opts = [str(o).strip() for o in raw_options if str(o).strip()]
            fallbacks = [
                "Không có phương án nào đúng",
                "Tất cả các phương án trên",
                "Chưa đủ dữ liệu kết luận",
                "Ý kiến khác",
            ]
            for fb in fallbacks:
                if len(opts) >= 4:
                    break
                if fb not in opts:
                    opts.append(fb)
            while len(opts) < 4:
                opts.append(f"Phương án {len(opts) + 1}")
            opts = opts[:4]

            # 3. Ensure uniqueness by automatically adding suffix if duplicates exist
            seen = set()
            unique_opts = []
            for i, opt in enumerate(opts):
                if opt in seen:
                    opt = f"{opt} ({i + 1})"
                seen.add(opt)
                unique_opts.append(opt)
            data["options"] = unique_opts

        # Normalize explanation if missing
        exp = data.get("explanation")
        if not exp or len(str(exp).strip()) < 3:
            data["explanation"] = "Dựa trên nội dung tài liệu."

        return data

    @field_validator("options")
    @classmethod
    def unique_options(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("options must be unique. Ensure all 4 options in each question are completely distinct and unique.")
        return v


class QuizOutput(BaseModel):
    questions: list[QuizItem] = Field(min_length=1, max_length=10)

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"questions": data}
        if isinstance(data, dict):
            if "questions" in data and isinstance(data["questions"], list):
                return data
            for k in ["quiz", "items", "data", "questions_list"]:
                if k in data and isinstance(data[k], list):
                    return {"questions": data[k]}
        return data


def build_fallback_quiz(text: str, num_questions: int = 3) -> QuizOutput:
    """Build a deterministic fallback quiz directly from document sentences."""
    num_questions = max(1, min(10, int(num_questions)))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    all_sentences: list[str] = []
    for p in paragraphs:
        clean_p = re.sub(r"^#+\s+.*$", "", p, flags=re.MULTILINE).strip()
        sents = [s.strip() for s in re.split(r"(?<=[.!?;\n])\s+", clean_p) if len(s.strip()) >= 15]
        for s in sents:
            cleaned = re.sub(r"\s+", " ", s).strip(" -*│┌┐└┘─#")
            if cleaned and cleaned not in all_sentences:
                all_sentences.append(cleaned[:160])

    if len(all_sentences) < 4:
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-*# ")
            if len(cleaned) >= 10 and cleaned not in all_sentences:
                all_sentences.append(cleaned[:160])

    if not all_sentences:
        all_sentences = [
            "Tài liệu cung cấp các nguyên lý và phương pháp học tập hiệu quả.",
            "Phương pháp Active Recall giúp tăng cường khả năng truy xuất thông tin.",
            "Lặp lại ngắt quãng (Spaced Repetition) củng cố trí nhớ dài hạn.",
            "Kỹ thuật Feynman giúp đơn giản hóa và làm sâu sắc hiểu biết.",
        ]

    questions: list[QuizItem] = []
    total_sents = len(all_sentences)

    for i in range(num_questions):
        correct_sentence = all_sentences[i % total_sents]
        distractors = []
        for offset in [1, 2, 3, 4, 5]:
            d_candidate = all_sentences[(i + offset) % total_sents]
            if d_candidate != correct_sentence and d_candidate not in distractors:
                distractors.append(d_candidate)
            if len(distractors) == 3:
                break

        generic_distractors = [
            "Thông tin này hoàn toàn không được đề cập trong tài liệu",
            "Nội dung này trái ngược với các nguyên lý được trình bày",
            "Đây là nhận định chưa được khoa học và tài liệu kiểm chứng",
        ]
        for gd in generic_distractors:
            if len(distractors) >= 3:
                break
            if gd not in distractors:
                distractors.append(gd)

        correct_idx = i % 4
        opts = list(distractors[:3])
        opts.insert(correct_idx, correct_sentence)

        q_item = QuizItem(
            question="Theo tài liệu, phát biểu nào sau đây là chính xác?",
            options=opts,
            correct_index=correct_idx,
            explanation=f"Chính xác theo nội dung: \"{correct_sentence}\".",
        )
        questions.append(q_item)

    return QuizOutput(questions=questions)


async def generate_quiz(text: str, num_questions: int = 5) -> QuizOutput:
    """Generate and validate the requested number of quiz questions with deterministic fallback."""
    num_questions = max(1, min(10, int(num_questions)))
    prompt = build_quiz_prompt(text, num_questions)
    response_schema = QuizOutput.model_json_schema()
    response_schema["required"] = ["questions"]
    response_schema["properties"]["questions"]["minItems"] = num_questions
    response_schema["properties"]["questions"]["maxItems"] = num_questions
    try:
        quiz = await generate_structured(
            prompt,
            QuizOutput,
            max_retries=2,
            max_new_tokens=min(1536, max(640, num_questions * 220)),
            response_schema=response_schema,
            temperature=0.35,
        )
        if len(quiz.questions) != num_questions:
            raise GenerationError(
                f"Quiz returned {len(quiz.questions)} questions; expected {num_questions}",
                reason="invalid_output",
            )
        return quiz
    except Exception as exc:
        logger.warning("Quiz generation via LLM failed, using fallback: %s", exc)
        return build_fallback_quiz(text, num_questions)


async def generate_quiz_and_store(doc_id: str, text: str, num_questions: int = 5) -> dict:
    """Generate quiz and store it in SQLite. Returns quiz dict."""
    from app.db.sqlite_store import insert_quiz

    quiz = await generate_quiz(text, num_questions)
    quiz_id = uuid.uuid4().hex[:12]
    insert_quiz(quiz_id, doc_id, [q.model_dump() for q in quiz.questions])

    return {
        "quiz_id": quiz_id,
        "doc_id": doc_id,
        "questions": [q.model_dump() for q in quiz.questions],
    }
