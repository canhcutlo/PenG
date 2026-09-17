# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

"""Quiz generation, discovery, grading, and persistence."""
import json
import uuid

from app.db.chunk_store import get_chunks_for_doc
from app.db.sqlite_store import (
    count_quiz_attempts,
    count_quizzes_for_document,
    get_document,
    get_quiz,
    insert_quiz,
    insert_quiz_result,
    list_quiz_attempts,
    list_quizzes_for_document,
    log_activity,
)
from app.models.schemas import (
    Quiz,
    QuizAttempt,
    QuizAttemptListResponse,
    QuizDiscoveryResponse,
    QuizResult,
    QuizSummary,
)
from app.services.extractor import extract, get_text_from_result
from app.services.file_storage import get_document_file_path
from app.services.quiz_gen import generate_quiz


class QuizContentError(ValueError):
    pass


async def create_quiz(doc_id: str, num_questions: int, user_id: str) -> Quiz:
    doc = get_document(doc_id, user_id)
    if not doc:
        raise LookupError(f"Document {doc_id} not found")
    chunks = get_chunks_for_doc(doc_id, user_id)
    text = "\n\n".join(chunk["text"] for chunk in chunks).strip()
    if not text:
        result = await extract(str(get_document_file_path(doc_id)), doc["category"])
        text = get_text_from_result(result)
    if not text.strip():
        raise QuizContentError("No text extracted from document")

    generated = await generate_quiz(text, num_questions=num_questions)
    quiz_id = uuid.uuid4().hex[:12]
    questions = [{"id": i, **question.model_dump()} for i, question in enumerate(generated.questions)]
    insert_quiz(quiz_id, doc_id, questions, user_id)
    log_activity(doc_id, "quizzed", user_id, {"quiz_id": quiz_id, "num_questions": num_questions})
    return Quiz(quiz_id=quiz_id, doc_id=doc_id, questions=questions)


def discover_quizzes(doc_id: str, user_id: str, limit: int, offset: int) -> QuizDiscoveryResponse | None:
    if not get_document(doc_id, user_id):
        return None
    total = count_quizzes_for_document(doc_id, user_id)
    rows = list_quizzes_for_document(doc_id, user_id, limit, offset) if total else []
    return QuizDiscoveryResponse(
        doc_id=doc_id,
        total=total,
        limit=limit,
        offset=offset,
        quizzes=[QuizSummary(**row) for row in rows],
    )


def list_attempts(quiz_id: str, user_id: str, limit: int, offset: int) -> QuizAttemptListResponse | None:
    if not get_quiz(quiz_id, user_id):
        return None
    rows = list_quiz_attempts(quiz_id, user_id, limit, offset)
    return QuizAttemptListResponse(
        quiz_id=quiz_id,
        total=count_quiz_attempts(quiz_id, user_id),
        limit=limit,
        offset=offset,
        attempts=[QuizAttempt(**row) for row in rows],
    )


def get_owned_quiz(quiz_id: str, user_id: str) -> Quiz | None:
    row = get_quiz(quiz_id, user_id)
    return Quiz(quiz_id=quiz_id, doc_id=row["doc_id"], questions=row["questions"]) if row else None


def grade_quiz(quiz_id: str, answers: list[int], user_id: str) -> QuizResult | None:
    quiz = get_quiz(quiz_id, user_id)
    if not quiz:
        return None
    correct = []
    incorrect = []
    for index, question in enumerate(quiz["questions"]):
        target = question["correct_index"]
        (correct if index < len(answers) and answers[index] == target else incorrect).append(index)
    score = len(correct)
    total = len(quiz["questions"])
    insert_quiz_result(quiz_id, json.dumps(answers), score, user_id)
    log_activity(quiz["doc_id"], "quizzed", user_id, {"quiz_id": quiz_id, "score": score, "total": total})
    return QuizResult(
        quiz_id=quiz_id,
        score=score,
        total=total,
        correct=correct,
        incorrect=incorrect,
    )
