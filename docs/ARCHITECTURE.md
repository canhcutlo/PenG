# PenG Architecture

## Scope

PenG is a Colab-friendly FastAPI application for turning learning media into
searchable study material. The frontend is static HTML/JavaScript, not a
React SPA. The server mounts `static/` at `/` and exposes JSON APIs under
`/api`.

## Runtime Flow

```text
Browser
  -> FastAPI upload endpoint
  -> SQLite document + job metadata
  -> background thread
       -> extract audio/image/PDF/video text
       -> chunk and index with LightRAG 1.5.5
       -> persistent NanoVectorDB in lightrag_data/
  -> query / quiz / mindmap / history APIs
  -> static HTML/JavaScript renders results
```

## Components

| Area | Implementation | Responsibility |
| --- | --- | --- |
| HTTP server | FastAPI + Uvicorn | API, health check, static file serving |
| Upload/jobs | `app/routers/upload.py`, `app/services/processing.py` | Validate and store media; report queued, processing, completed, or failed jobs |
| Extraction | `app/services/extractor.py`, `stt.py`, `ocr.py`, `video.py` | STT, OCR/native PDF text, and video scene/keyframe text |
| Retrieval | LightRAG `lightrag-hku==1.5.5` | Index and query chunks in `naive` vector mode by default |
| Vector storage | LightRAG NanoVectorDB | File-based persistent storage under the configured working directory; ChromaDB is not used |
| Generation | Transformers + Qwen2.5-3B-Instruct | Lazy-loaded answer, quiz, and mindmap generation; 4-bit CUDA loading when enabled |
| Embeddings | `keepitreal/vietnamese-sbert` | Vietnamese-capable embeddings; configured dimension is 768 |
| Structured output | Pydantic validation and bounded retry; optional Instructor adapter | Validates generated quiz and related structured results |
| Persistence | SQLite in `peng_history.db` by default | Documents, processing jobs, activities, quizzes, and quiz results |
| Client | `static/index.html` | Upload, polling, query, quiz, mindmap, history, and export interactions |
| Colab access | `pyngrok` | Optional public tunnel; token must come from environment/secrets |

## API Surface

- `GET /api/health`
- `POST /api/upload`
- `GET /api/jobs/{job_id}`
- `GET /api/query?q=...&top_k=...&doc_id=...`
- `POST /api/quiz/generate?doc_id=...`
- `GET /api/quiz/{quiz_id}`
- `POST /api/quiz/{quiz_id}/submit`
- `GET /api/mindmap/{doc_id}`
- `GET /api/history`
- `POST /api/history`

## Operational Boundaries

Models are lazy-loaded, so health checks and unit tests do not need to load
the LLM. Media extraction and indexing run through a worker thread so job
polling remains responsive. The MVP has no authentication, user isolation, or
production queue; those are deployment responsibilities and known limits.
