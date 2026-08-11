# Contributing to PenG

PenG is a FastAPI learning application with a static HTML/JavaScript client.
Contributions that improve reliability, reproducibility, accessibility, or
Vietnamese/English learning quality are welcome.

## Before You Start

- Check existing issues before opening a new one.
- For a security vulnerability, do not open a public issue. Follow
  [SECURITY.md](SECURITY.md).
- Keep pull requests focused and do not commit credentials, model caches,
  uploaded media, SQLite databases, or generated LightRAG data.

## Local Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Python 3.10 or newer is required. Python 3.14 uses the Tesseract/EasyOCR
path; the optional Surya OCR dependency is intended for compatible Python
versions and the Colab environment.

## Checks

Run the fast checks before submitting a change:

```powershell
python -m compileall app
pytest tests/ -v -m "not integration"
```

Integration tests may download models or require external media tooling:

```powershell
pytest tests/ -v
```

Document any test that could not run, including the Python, CUDA, and model
environment used.

## Change Guidelines

- Keep API routes thin; put business logic in `app/services/` and persistence
  in `app/db/`.
- Preserve the current stack unless a change is discussed: FastAPI, LightRAG
  1.5.5 with NanoVectorDB, SQLite, static HTML/JavaScript, and the configured
  Qwen/Vietnamese SBERT defaults.
- Update documentation and tests when behavior or an API contract changes.
- Never add secrets to source, notebooks, issues, logs, or screenshots.
- Use clear commit messages and explain compatibility or migration concerns in
  the pull request.

## Pull Requests

A pull request should describe the user-visible change, affected endpoints or
pipeline stages, tests run, and any known limitations. Keep generated files
out of the patch unless they are explicitly part of the change.
