# Copyright (c) 2026 Team PenG - Nguyễn Trung Thành
# SPDX-License-Identifier: MIT

from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import (
    Quiz,
    QuizAttemptListResponse,
    QuizDiscoveryResponse,
    QuizSubmission,
    QuizResult,
)
from app.services.auth import require_auth, verify_csrf
from app.services.quizzes import (
    create_quiz,
    discover_quizzes,
    get_owned_quiz,
    grade_quiz,
    list_attempts,
    QuizContentError,
)

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
    try:
        if num_questions < 1 or num_questions > 10:
            raise HTTPException(status_code=422, detail="num_questions must be between 1 and 10")
        return await create_quiz(doc_id, num_questions, user["user_id"])
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except QuizContentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
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
    result = discover_quizzes(doc_id, user["user_id"], limit, offset)
    if not result:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return result


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
    result = list_attempts(quiz_id, user["user_id"], limit, offset)
    if not result:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
    return result


@router.get("/quiz/{quiz_id}", response_model=Quiz)
async def get_quiz_endpoint(quiz_id: str, user: dict = Depends(require_auth)):
    """Get a persisted quiz by ID."""
    quiz = get_owned_quiz(quiz_id, user["user_id"])
    if not quiz:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
    return quiz


@router.post("/quiz/{quiz_id}/submit", response_model=QuizResult)
async def submit_quiz_endpoint(
    request: Request,
    quiz_id: str,
    submission: QuizSubmission,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Submit answers, grade server-side, persist result + log activity."""
    result = grade_quiz(quiz_id, submission.answers, user["user_id"])
    if not result:
        raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
    return result
