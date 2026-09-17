# PenG Architecture

## Scope

PenG is a Colab-friendly FastAPI application for turning learning media into
searchable study material. The frontend is static HTML/JavaScript, not a
React SPA. The server mounts `static/` at `/` and exposes JSON APIs under
`/api`.

## Runtime Flow

```text
Browser
  -> FastAPI authentication and CSRF checks
  -> upload endpoint
  -> SQLite user, document, and job metadata
  -> background thread
       -> extract audio/image/PDF/video text
       -> chunk and index with LightRAG 1.5.5
       -> per-user NanoVectorDB in lightrag_data/u/{user_id}/
       -> generate versioned summary and mindmap artifacts
       -> update knowledge node and related-document edges
  -> document chat / quiz / mindmap / history APIs
  -> static HTML/JavaScript renders results
```

## Components

| Area | Implementation | Responsibility |
| --- | --- | --- |
| HTTP server | FastAPI + Uvicorn | API, health check, static file serving |
| Authentication | Argon2 password hash + opaque SQLite sessions | HttpOnly session cookie, CSRF token, ownership checks, login rate limit |
| Upload/jobs | `app/routers/upload.py`, `app/services/processing.py` | Validate and store media; report queued, processing, completed, or failed jobs |
| Extraction | `app/services/extractor.py`, `stt.py`, `ocr.py`, `video.py` | STT, OCR/native PDF text, and video scene/keyframe text |
| Retrieval | LightRAG `lightrag-hku==1.5.5` | Index and query chunks in `naive` vector mode by default |
| Vector storage | LightRAG NanoVectorDB | File-based persistent storage under the configured working directory; ChromaDB is not used |
| Generation | Transformers + Qwen2.5-1.5B-Instruct | Branch default; lazy-loaded answer, quiz, and mindmap generation; 4-bit CUDA loading when enabled |
| Embeddings | `keepitreal/vietnamese-sbert` | Vietnamese-capable embeddings; configured dimension is 768 |
| Structured output | Pydantic validation and bounded retry; optional Instructor adapter | Validates generated quiz and related structured results |
| Artifacts | `app/services/artifacts.py` | Versioned summary/mindmap generation; artifact failure does not fail an indexed document |
| Chat/knowledge | `app/services/chat.py`, `knowledge.py`, `faithfulness.py` | Evidence-based document chat, same-user related documents, citation validation |
| Persistence | SQLite in `peng_history.db` by default | Users, sessions, documents, jobs, chunks, activities, quizzes, artifacts, chat, and knowledge metadata |
| Client | `static/index.html` + ES modules | Authentication, upload, polling, document study, chat, quiz, mindmap, history, and export interactions |
| Colab access | `pyngrok` | Optional public tunnel; token must come from environment/secrets |

## API Surface

- `GET /api/health`
- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
- `POST /api/upload`
- `GET /api/jobs/{job_id}`
- `GET /api/documents`, `GET /api/documents/{doc_id}/source`
- `GET /api/documents/{doc_id}/artifacts`, `GET /api/documents/{doc_id}/summary`
- `POST /api/documents/{doc_id}/artifacts/regenerate`
- `GET /api/query?q=...&top_k=...&doc_id=...`
- `POST /api/quiz/generate?doc_id=...`
- `GET /api/quiz/{quiz_id}`
- `POST /api/quiz/{quiz_id}/submit`
- `GET /api/mindmap/{doc_id}`
- `GET /api/history`
- `POST /api/history`
- `POST /api/chat/sessions`, `GET /api/chat/sessions`, `GET /api/chat/{session_id}`
- `POST /api/chat/{session_id}/messages`
- `GET /api/knowledge/nodes/{doc_id}`, `GET /api/knowledge/related/{doc_id}`

## Operational Boundaries

Models are lazy-loaded, so health checks and unit tests do not need to load
the LLM. Media extraction and indexing run through an in-process worker thread
so job polling remains responsive. Routers handle HTTP concerns and call domain
services; services own orchestration and database access. Documents, chunks,
artifacts, quizzes, chat, knowledge nodes, and RAG directories are scoped by
user. The in-process worker is intentionally not a production queue: multi-host
deployment requires moving jobs to an external durable queue.
