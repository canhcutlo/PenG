"""Pydantic schemas for all API request/response models."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal



class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class UserMe(BaseModel):
    user_id: str
    username: str


class AuthResponse(BaseModel):
    user_id: str
    username: str


class Document(BaseModel):
    doc_id: str
    filename: str
    original_name: str
    category: Literal["audio", "image", "pdf", "video"]
    file_size: int
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
    source: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    related_chunks: list[QueryResult] = []




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
    answers: list[int]


class QuizResult(BaseModel):
    quiz_id: str
    score: int
    total: int
    correct: list[int]
    incorrect: list[int]




class MindmapNode(BaseModel):
    content: str
    level: int
    children: list["MindmapNode"] = []




class Artifact(BaseModel):
    artifact_id: str
    doc_id: str
    user_id: str
    type: Literal["summary", "mindmap"]
    version: int
    status: Literal["queued", "processing", "completed", "failed"]
    content: str | None = None
    input_snapshot: dict | None = None
    language: str | None = None
    model_id: str | None = None
    llm_config: dict | None = None
    generation_params: dict | None = None
    prompt_version: str | None = None
    attempts: int = 0
    error_message: str | None = None
    created_at: datetime | None = None




class LearningActivity(BaseModel):
    id: int | None = None
    doc_id: str
    filename: str
    action: Literal["uploaded", "viewed", "quizzed", "mindmapped"]
    created_at: datetime | None = None




class ChatSessionCreate(BaseModel):
    doc_id: str
    title: str | None = None


class ChatSession(BaseModel):
    session_id: str
    user_id: str
    doc_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    mode: Literal["document_and_related"] = "document_and_related"


class RelatedDocument(BaseModel):
    doc_id: str
    title: str | None = None
    relation_type: str


class RelatedNode(BaseModel):
    node_id: str
    document_id: str
    title: str | None = None
    relation_type: str


class ChatMessageResponse(BaseModel):
    message_id: str
    session_id: str
    answer: str
    citations: list[Citation] = []
    related_documents: list[RelatedDocument] = []
    related_nodes: list[RelatedNode] = []
    warnings: list[str] = []
    model_id: str | None = None
    prompt_version: str | None = None


class KnowledgeNodeResponse(BaseModel):
    node_id: str
    document_id: str
    title: str | None = None
    summary: str | None = None
    mindmap_markdown: str | None = None
    language: str | None = None
    labels: list[str] = []
    internal_consistency: float
    evidence_coverage: float
    extraction_quality: float
    status: str
    version: int
    created_at: datetime


class KnowledgeEdgeResponse(BaseModel):
    edge_id: str
    source_node_id: str
    source_doc_id: str
    target_node_id: str
    target_doc_id: str
    relation_type: str
    similarity_score: float
    evidence: dict
    status: str
    created_at: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: str
    status_code: int
