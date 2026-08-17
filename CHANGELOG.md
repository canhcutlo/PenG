# Changelog

All notable project changes are recorded here. The project does not currently
publish versioned releases; entries are grouped by delivery milestone.

## [Unreleased]

- Added optional CPU GGUF runtime via `llama-cpp-python` on branch
  `experiment/gguf-llama-cpp`. `LLM_RUNTIME` selects between `transformers`
  (default, CUDA-friendly) and `llama_cpp` (local GGUF). Added
  `requirements-cpu.txt`, `docs/CPU_GGUF.md`, `scripts/benchmark_llm.py`, and
  unit tests with a monkeypatched fake llama runtime.
- Made runtime paths (uploads, SQLite, LightRAG working dir) resolve relative to
  the project root when launched outside the repo root, while preserving absolute
  `.env` overrides. `StaticFiles` now uses an absolute path.
- Removed `surya-ocr` from `requirements.txt` to avoid the Pillow>=11 conflict on
  local Python 3.14+; kept it in `requirements-colab.txt` for Python 3.12.
- Documented ffmpeg and Tesseract `vie+eng` system dependencies.
- Corrected README: removed stale ChromaDB/chroma_store references, fixed API
  routes, pointed Colab install to `requirements-colab.txt`, and clarified the
  default OCR engine is tesseract.
- Fixed `embed()` return-type annotation to match the NumPy array it returns.
- Removed the unused `allowed_mime_types` setting.
- Added `tests/test_config.py` covering project-root path resolution.
- Added open-source project governance documentation: contribution guidance,
  security reporting, architecture, and AI pipeline notes.
- Added GitHub issue templates for reproducible bugs and scoped feature
  requests.
- Documented the current Colab-first runtime and its model/dependency limits.

## 2026-08-02

- Completed the static study workspace with upload, query, quiz, mindmap, and
  history tabs.
- Added mindmap Markdown and SVG downloads.
- Improved background job polling while extraction and indexing run.
- Switched the default language model to Qwen2.5-3B-Instruct and configured
  4-bit loading for a Colab T4 when CUDA is available.
- Removed the unused ChromaDB integration and retained LightRAG's persistent
  NanoVectorDB storage.

## 2026-08-01

- Implemented the FastAPI upload, processing-job, query, quiz, mindmap, and
  learning-history flows.
- Added audio transcription, image/PDF OCR, video scene/keyframe extraction,
  chunking, embeddings, and LightRAG retrieval.
- Added SQLite persistence and structured quiz/mindmap generation with
  validation and bounded retries.
- Added unit and model-marked integration tests.
