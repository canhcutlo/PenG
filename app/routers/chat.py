"""Chat endpoints: sessions and messages with evidence retrieval."""
from fastapi import APIRouter, HTTPException, Depends, Request
from app.models.schemas import ChatSessionCreate, ChatSession, ChatMessageCreate, ChatMessageResponse
from app.db.sqlite_store import get_document
from app.services.chat import (
    create_chat_session,
    list_chat_sessions,
    get_session_with_messages,
    post_chat_message,
)
from app.services.auth import require_auth, verify_csrf

router = APIRouter()


def _doc_title(doc_id: str, user_id: str) -> str | None:
    doc = get_document(doc_id, user_id)
    if not doc:
        return None
    return doc.get("original_name") or doc.get("filename")


def _require_csrf():
    def _check(request: Request):
        verify_csrf(request)
    return Depends(_check)


@router.post("/chat/sessions", response_model=ChatSession, status_code=201)
async def create_session(
    data: ChatSessionCreate,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Create a chat session scoped to a single document."""
    try:
        session = create_chat_session(user["user_id"], data.doc_id, data.title)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ChatSession(
        session_id=session["session_id"],
        user_id=session["user_id"],
        doc_id=session["document_id"],
        title=session.get("title"),
        doc_title=_doc_title(session["document_id"], session["user_id"]),
        created_at=session["created_at"],
        updated_at=session.get("updated_at"),
    )


@router.get("/chat/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    user: dict = Depends(require_auth),
):
    """List chat sessions for the current user."""
    rows = list_chat_sessions(user["user_id"], limit, offset)
    return [
        ChatSession(
            session_id=r["session_id"],
            user_id=r["user_id"],
            doc_id=r["document_id"],
            title=r.get("title"),
            doc_title=r.get("doc_title"),
            created_at=r["created_at"],
            updated_at=r.get("updated_at"),
        )
        for r in rows
    ]


@router.get("/chat/{session_id}")
async def get_session(
    session_id: str,
    user: dict = Depends(require_auth),
):
    """Get a chat session and its messages."""
    try:
        session, messages = await get_session_with_messages(user["user_id"], session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "session": ChatSession(
            session_id=session["session_id"],
            user_id=session["user_id"],
            doc_id=session["document_id"],
            title=session.get("title"),
            doc_title=_doc_title(session["document_id"], session["user_id"]),
            created_at=session["created_at"],
            updated_at=session.get("updated_at"),
        ),
        "messages": messages,
    }


@router.post("/chat/{session_id}/messages", response_model=ChatMessageResponse, status_code=201)
async def post_message(
    session_id: str,
    data: ChatMessageCreate,
    request: Request,
    user: dict = Depends(require_auth),
    _csrf=_require_csrf(),
):
    """Post a message and get an evidence-based answer."""
    content = data.content.strip() if data.content else ""
    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    try:
        result = await post_chat_message(
            user["user_id"], session_id, content, data.mode
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ChatMessageResponse(**result)
