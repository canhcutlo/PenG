from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import Quiz, QuizSubmission, QuizResult
from app.db.sqlite_store import get_quiz, insert_quiz_result, insert_quiz, get_document, log_activity
from app.services.file_storage import get_document_file_path
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
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {exc}")


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
