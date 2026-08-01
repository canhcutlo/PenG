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
            raise ValueError("options must be unique")
        return v


class QuizOutput(BaseModel):
    questions: list[QuizItem] = Field(min_length=1, max_length=10)


async def generate_quiz(text: str, num_questions: int = 5) -> QuizOutput:
    """Generate and validate quiz questions from text.

    Raises GenerationError when the model cannot produce valid JSON
    within the retry bound.
    """
    prompt = build_quiz_prompt(text, num_questions)
    quiz = await generate_structured(prompt, QuizOutput)
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
