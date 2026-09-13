# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import (
    Quiz,
    QuizAttempt,
    QuizAttemptListResponse,
    QuizDiscoveryResponse,
    QuizSubmission,
    QuizResult,
    QuizSummary,
)
from app.db.sqlite_store import (
    count_quiz_attempts,
    count_quizzes_for_document,
    get_quiz,
    insert_quiz_result,
    insert_quiz,
    get_document,
    list_quiz_attempts,
    list_quizzes_for_document,
    log_activity,
)
from app.services.file_storage import get_document_file_path
from app.db.chunk_store import get_chunks_for_doc
from app.services.quiz_gen import generate_quiz
from app.services.extractor import extract, get_text_from_result
from app.services.auth import require_auth, verify_csrf
import uuid
import json

router = APIRouter()


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.post("/quiz/generate", response_model=Quiz)
async def generate_quiz_endpoint(
    request: Request,
    doc_id: str,
    num_questions: int = 5,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Generate quiz questions and persist to SQLite."""
    doc = get_document(doc_id, user["user_id"])
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    try:
        if num_questions < 1 or num_questions > 10:
            raise HTTPException(status_code=422, detail="num_questions must be between 1 and 10")

        chunks = get_chunks_for_doc(doc_id, user["user_id"])
        text = "\n\n".join(chunk["text"] for chunk in chunks).strip()
        if not text:
            file_path = get_document_file_path(doc_id)
            result = await extract(str(file_path), doc["category"])
            text = get_text_from_result(result)
        if not text.strip():
            raise HTTPException(status_code=422, detail="No text extracted from document")

        quiz = await generate_quiz(text, num_questions=num_questions)
        quiz_id = uuid.uuid4().hex[:12]
        questions_data = [{"id": i, **q.model_dump()} for i, q in enumerate(quiz.questions)]
        insert_quiz(quiz_id, doc_id, questions_data, user["user_id"])
        log_activity(doc_id, "quizzed", user["user_id"], {"quiz_id": quiz_id, "num_questions": num_questions})

        return Quiz(quiz_id=quiz_id, doc_id=doc_id, questions=questions_data)
    except HTTPException:
        raise
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        reason = getattr(exc, "reason", "runtime")
        raise HTTPException(status_code=500, detail=f"Quiz generation failed ({reason}): {detail}")


@router.get("/documents/{doc_id}/quizzes", response_model=QuizDiscoveryResponse)
async def discover_document_quizzes(
    doc_id: str,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(require_auth),
):
    """List quizzes and aggregate attempt stats for an owned document."""
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(status_code=422, detail="limit must be 1..200 and offset must be non-negative")
    if not get_document(doc_id, user["user_id"]):
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    total = count_quizzes_for_document(doc_id, user["user_id"])
    if total == 0:
        return QuizDiscoveryResponse(
            doc_id=doc_id,
            total=0,
            limit=limit,
            offset=offset,
            quizzes=[],
        )
    rows = list_quizzes_for_document(doc_id, user["user_id"], limit, offset)
    return QuizDiscoveryResponse(
        doc_id=doc_id,
        total=total,
        limit=limit,
        offset=offset,
        quizzes=[QuizSummary(**row) for row in rows],
    )


@router.get("/quiz/{quiz_id}/attempts", response_model=QuizAttemptListResponse)
async def get_quiz_attempts_endpoint(
    quiz_id: str,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(require_auth),
):
    """List attempts for an owned quiz."""
    if limit < 1 or limit > 200 or offset < 0:
        raise HTTPException(status_code=422, detail="limit must be 1..200 and offset must be non-negative")
    quiz = get_quiz(quiz_id, user["user_id"])
    if not quiz:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
    rows = list_quiz_attempts(quiz_id, user["user_id"], limit, offset)
    return QuizAttemptListResponse(
        quiz_id=quiz_id,
        total=count_quiz_attempts(quiz_id, user["user_id"]),
        limit=limit,
        offset=offset,
        attempts=[QuizAttempt(**row) for row in rows],
    )


@router.get("/quiz/{quiz_id}", response_model=Quiz)
async def get_quiz_endpoint(quiz_id: str, user: dict = Depends(require_auth)):
    """Get a persisted quiz by ID."""
    quiz = get_quiz(quiz_id, user["user_id"])
    if not quiz:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
    return Quiz(quiz_id=quiz_id, doc_id=quiz["doc_id"], questions=quiz["questions"])


@router.post("/quiz/{quiz_id}/submit", response_model=QuizResult)
async def submit_quiz_endpoint(
    request: Request,
    quiz_id: str,
    submission: QuizSubmission,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Submit answers, grade server-side, persist result + log activity."""
    quiz = get_quiz(quiz_id, user["user_id"])
    if not quiz:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")

    questions = quiz["questions"]
    correct_answers = [q["correct_index"] for q in questions]
    user_answers = submission.answers

    correct_indices = []
    incorrect_indices = []
    for i, correct in enumerate(correct_answers):
        user_ans = user_answers[i] if i < len(user_answers) else None
        if user_ans == correct:
            correct_indices.append(i)
        else:
            incorrect_indices.append(i)

    score = len(correct_indices)
    total = len(questions)

    insert_quiz_result(quiz_id, json.dumps(user_answers), score, user["user_id"])
    log_activity(quiz["doc_id"], "quizzed", user["user_id"], {"quiz_id": quiz_id, "score": score, "total": total})

    return QuizResult(
        quiz_id=quiz_id,
        score=score,
        total=total,
        correct=correct_indices,
        incorrect=incorrect_indices,
    )
