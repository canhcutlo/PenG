"""Pydantic schemas for all API request/response models."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

# ─── Document & Job ────────────────────────────────────────────────────────


class Document(BaseModel):
    doc_id: str
    filename: str
    original_name: str
    category: Literal["audio", "image", "pdf", "video"]
    file_size: int  # bytes
    checksum_sha256: str
    status: Literal["queued", "processing", "completed", "failed"]
    created_at: datetime
    updated_at: datetime | None = None


class DocumentCreate(BaseModel):
    filename: str
    original_name: str
    category: Literal["audio", "image", "pdf", "video"]
    file_size: int
    checksum_sha256: str


class Job(BaseModel):
    job_id: str
    doc_id: str
    job_type: Literal["extract", "index"]
    status: Literal["queued", "processing", "completed", "failed"]
    progress: int = Field(default=0, ge=0, le=100)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class JobCreate(BaseModel):
    doc_id: str
    job_type: Literal["extract", "index"]


# ─── Upload ────────────────────────────────────────────────────────────────


class UploadResponse(BaseModel):
    doc_id: str
    job_id: str
    filename: str
    category: str
    status: str = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    doc_id: str
    status: str
    progress: int
    error_message: str | None = None


# ─── Query ─────────────────────────────────────────────────────────────────


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    page: int | None = None
    scene: int | None = None
    timestamp: float | None = None
    metadata_json: dict | None = None


class Citation(BaseModel):
    doc_id: str
    page: int | None = None
    scene: int | None = None
    timestamp: float | None = None
    chunk_text: str


class QueryResult(BaseModel):
    doc_id: str
    chunk: str
    score: float
    source: str  # "audio", "pdf", "image", "video"


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    related_chunks: list[QueryResult] = []


# ─── Quiz ──────────────────────────────────────────────────────────────────


class QuizQuestion(BaseModel):
    id: int | None = None
    question: str
    options: list[str]
    correct_index: int
    explanation: str


class Quiz(BaseModel):
    quiz_id: str
    doc_id: str
    questions: list[QuizQuestion]


class QuizSubmission(BaseModel):
    quiz_id: str
    answers: list[int]  # selected option indices


class QuizResult(BaseModel):
    quiz_id: str
    score: int
    total: int
    correct: list[int]
    incorrect: list[int]


# ─── Mindmap ───────────────────────────────────────────────────────────────


class MindmapNode(BaseModel):
    content: str
    level: int
    children: list["MindmapNode"] = []


# ─── History ───────────────────────────────────────────────────────────────


class LearningActivity(BaseModel):
    id: int | None = None
    doc_id: str
    filename: str
    action: Literal["uploaded", "viewed", "quizzed", "mindmapped"]
    created_at: datetime | None = None


# ─── Error ─────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
