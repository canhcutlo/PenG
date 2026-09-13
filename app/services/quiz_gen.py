# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Quiz generation with structured output validation."""
import uuid
from pydantic import BaseModel, Field, field_validator

from app.services.prompts import build_quiz_prompt
from app.services.structured import generate_structured, GenerationError


class QuizItem(BaseModel):
    question: str = Field(min_length=3)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=3)

    @field_validator("options")
    @classmethod
    def unique_options(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("options must be unique. Ensure all 4 options in each question are completely distinct and unique.")
        return v


class QuizOutput(BaseModel):
    questions: list[QuizItem] = Field(min_length=1, max_length=10)


async def generate_quiz(text: str, num_questions: int = 5) -> QuizOutput:
    """Generate and validate the requested number of quiz questions."""
    num_questions = max(1, min(10, int(num_questions)))
    prompt = build_quiz_prompt(text, num_questions)
    response_schema = QuizOutput.model_json_schema()
    response_schema["required"] = ["questions"]
    response_schema["properties"]["questions"]["minItems"] = num_questions
    response_schema["properties"]["questions"]["maxItems"] = num_questions
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
