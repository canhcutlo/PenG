# AI Pipeline

## Overview

PenG accepts audio, images, PDFs, video, text, Markdown, and DOCX. Upload
processing is asynchronous: the authenticated API stores user-scoped metadata
in SQLite, creates a job, and runs extraction, indexing, and artifact generation
in the background. The frontend polls `GET /api/jobs/{job_id}`.

## Extraction

| Input | Current path | Output |
| --- | --- | --- |
| Audio | `faster-whisper`, model `base` | Transcript and timing/language metadata when available |
| Image | Tesseract by default, with EasyOCR/Surya support depending on runtime | OCR text and source metadata |
| PDF | Native PyMuPDF text first; OCR for pages without usable text | Page-aware text |
| Text/Markdown/DOCX | Native text or archive/XML extraction | Ordered document text |
| Video | PySceneDetect/MoviePy scene or sampled keyframes, then OCR | Keyframe text with scene/time metadata |

Extracted content is normalized to text, split into bounded chunks, and passed
to indexing. Empty extraction fails the processing job rather than creating an
empty index entry.

## Retrieval and Embeddings

The configured embedding model is `keepitreal/vietnamese-sbert` with a verified
768-dimensional output. LightRAG 1.5.5 is initialized lazily and uses
`NanoVectorDBStorage` in its working directory. Queries use LightRAG's `naive`
mode by default, which is vector retrieval without graph traversal. ChromaDB
is not part of the current runtime.

Retrieval is scoped to the authenticated user's RAG directory and persisted
source chunks. Query and chat normalize those chunks into stable evidence IDs.
Structured answers may only cite supplied IDs; invalid IDs are removed and an
unsupported answer is downgraded to an explicit no-context response. This is an
evidence guard, not a factual-truth guarantee for the uploaded source itself.

## Generation

The default causal language model on this branch is `Qwen/Qwen2.5-1.5B-Instruct`. Transformers
loads it only when generation is requested. On CUDA, the configured path uses
BitsAndBytes 4-bit quantization to fit a Colab T4; CPU fallback is available
but slower and may require more memory.

Prompts and generators cover answers, quizzes, summaries, mindmaps, and chat.
Structured output is parsed as JSON and validated with Pydantic, with a bounded
retry policy. Completed summary and mindmap artifacts are versioned in SQLite;
generation failure does not invalidate completed extraction or indexing.
Quiz validation requires four unique options and a valid answer index. Mindmap
Markdown is sanitized before it is rendered by the browser.

## Reproducibility and Limits

- Unit tests use deterministic fallbacks and do not require large model
  downloads; model-backed tests are marked `integration`.
- Exact output varies with model versions, hardware, quantization, OCR engine,
  and source quality.
- Session cookies, CSRF checks, ownership filters, and per-user RAG directories
  prevent normal cross-user access; this is not a production security audit.
- The application does not claim that source documents or model summaries are
  factually correct outside the evidence supplied by those documents.
- Model and OCR licenses/terms must be reviewed before redistribution or a
  hosted deployment.
