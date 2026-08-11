# AI Pipeline

## Overview

PenG accepts audio, images, PDFs, and video. Upload processing is asynchronous:
the API stores metadata in SQLite, creates a job, and runs extraction and
indexing in the background. The frontend polls `GET /api/jobs/{job_id}`.

## Extraction

| Input | Current path | Output |
| --- | --- | --- |
| Audio | `faster-whisper`, model `base` | Transcript and timing/language metadata when available |
| Image | Tesseract by default, with EasyOCR/Surya support depending on runtime | OCR text and source metadata |
| PDF | Native PyMuPDF text first; OCR for pages without usable text | Page-aware text |
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

The query service requests references and returns an answer-shaped response.
When the model cannot produce a contextual answer, it falls back to relevant
retrieved text or an explicit no-context message. Citation extraction is
currently lightweight and depends on source hints in generated text; it should
not be treated as a provenance guarantee.

## Generation

The default causal language model is `Qwen/Qwen2.5-3B-Instruct`. Transformers
loads it only when generation is requested. On CUDA, the configured path uses
BitsAndBytes 4-bit quantization to fit a Colab T4; CPU fallback is available
but slower and may require more memory.

Prompts and generators cover answers, quizzes, and mindmaps. Structured output
is parsed as JSON and validated with Pydantic, with a bounded retry policy.
Quiz validation requires four unique options and a valid answer index. Mindmap
Markdown is sanitized before it is rendered by the browser.

## Reproducibility and Limits

- Unit tests use deterministic fallbacks and do not require large model
  downloads; model-backed tests are marked `integration`.
- Exact output varies with model versions, hardware, quantization, OCR engine,
  and source quality.
- The MVP does not claim factual correctness, complete citations, or safe
  handling of sensitive documents.
- Model and OCR licenses/terms must be reviewed before redistribution or a
  hosted deployment.
