# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-06

### Added
- **Open-Source Compliance (SPDX)**: Added standard `SPDX-License-Identifier: MIT` headers to 100% of project source files (`.py` and `static/index.html`).
- **PEP 517 / PEP 621 Standard Packaging**: Configured modern `pyproject.toml` metadata, `setuptools` build-system, entrypoints, and package discovery.
- **CLI Entrypoint (`peng-server`)**: Added `run_server()` in `app/main.py` allowing server launch from any directory via `peng-server` CLI with configurable `--host`, `--port`, and `--reload` options.
- **GGUF CPU Runtime via `llama-cpp-python`**: Support for local GGUF models on CPU without requiring dedicated GPU hardware, benchmark scripts (`scripts/benchmark_llm.py`), and documentation in `docs/CPU_GGUF.md`.
- **Evidence Faithfulness Guard**: Added evidence normalization and verification guard for RAG query and chat to prevent hallucinated answers and eligibility polarity flips.
- **Per-User Knowledge Graph & Document Chatbot**: Added user-isolated SQLite storage, knowledge graph nodes/edges, and document conversational chat.
- **Release Packaging Tool**: Added `scripts/package_release.py` to bundle clean open-format source distribution archives (`.tar.gz`).
- **SPDX Compliance Verifier**: Added `scripts/verify_spdx_headers.py` for automated license header auditing.

### Changed
- Added `models/` and `*.gguf` to `.gitignore` to prevent bundling large weight files.
- Improved processing progress, title generation, and multilingual chat response consistency.
- Standardized runtime paths to resolve reliably from repository root or absolute environment paths.

### Fixed
- Fixed type annotation in `app/services/artifacts.py` using `collections.abc.Callable`.
- Fixed `embed()` return-type annotation to match NumPy array required by NanoVectorDB / LightRAG.

## [0.0.1-pre-release] - 2026-08-11

### Added
- Initial pre-release version of PenG (corresponding to GitHub tag `V0.0.1_Pre-release`).
- Full multimodal study workspace with audio transcription (faster-whisper), OCR (pytesseract/EasyOCR), video processing (scenedetect + MoviePy), and PDF text extraction.
- RAG integration with LightRAG and persistent NanoVectorDB storage.
- Automated quiz generation, evaluation scoring, and markdown mindmap visualization.
- SQLite history persistence and session-based authentication.
- Initial suite of unit tests and model integration tests.
