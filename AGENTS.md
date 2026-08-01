# AGENTS.md – PenG

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Critical constraints

- **Python >=3.10** required (LightRAG and scenedetect enforce this).
- **PySceneDetect** is installed as `pip install scenedetect` — NOT `pyscenedetect`.
- **"Unlimited-OCR" does not exist** as a library. **Surya OCR** (`pip install surya`) works on Python <=3.11. On Python 3.14+ use **pytesseract** or **EasyOCR** as the default OCR engine. `pymupdf` handles PDFs and `Pillow` handles images.
- **CUDA**: faster-whisper needs CUDA 12 + cuDNN 9 (via ctranslate2 >=4.5). On Colab T4, pin `ctranslate2==3.24.0` if CUDA 11 is detected.
- **MoviePy v2** has breaking changes from v1; this project uses v2 (`pip install moviepy`).
- **Surya-ocr requires Pillow<11**. Conflict with `Pillow>=11.0` (needed for Python 3.14). Solution:
  - `requirements.txt`: `Pillow>=11.0` (local dev, Python 3.14). Do NOT install `surya-ocr` here.
  - `requirements-colab.txt`: `Pillow>=10.0,<11` (Colab, Python 3.12). Surya works on Colab.

## Architecture

```
Upload → Extract (STT/OCR/Video) → Index (LightRAG → NanoVectorDB)
                                    ↓
User Query → LightRAG → LLM (Llama/Qwen) → Structured Output (JSON+Pydantic / Instructor)
                                               ↓
                                    Mindmap (Markmap JS) + Quiz (react-quiz-component)
```

- **FastAPI** backend, **SQLite** for learning history, **LightRAG (NanoVectorDB)** for vector storage.
  ChromaDB is deprecated in lightrag-hku 1.5.5 (`kg/deprecated/`) and is NOT used for RAG.
- **Frontend is static JS** (markmap-lib, react-quiz-component) served from `/static/` — NOT a React SPA.
- LLM structured output goes through `app/services/structured.py`: JSON + Pydantic validate +
  bounded retry (works with any local model). **Instructor** is only used when an
  OpenAI-compatible endpoint (Ollama/vLLM) is configured (`use_instructor=true`).

## Dev commands

```powershell
# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run unit tests (skip AI model downloads)
pytest tests/ -v -m "not integration"

# Run all tests including integration (downloads/runs AI models)
pytest tests/ -v

# Run a single test
pytest tests/test_api.py::test_upload_audio -v
```

## Google Colab workflow

- The canonical test environment is **Google Colab with GPU T4**.
- Use `notebooks/peng_colab.ipynb` to clone, install, and serve.
- In Colab, FastAPI is exposed via **ngrok** (`pyngrok`).
- GPU memory is tight (T4 ≈15GB): load the LLM in 4-bit quantization (`bitsandbytes` + `transformers`).

## Package gotchas

| Intent | Correct package |
|---|---|
| OCR images/PDFs | `surya` + `pymupdf` + `Pillow` (Python <=3.11) or `pytesseract`/`easyocr` (Python 3.14+) |
| Scene detection | `scenedetect` (NOT pyscenedetect) |
| Speech-to-text | `faster-whisper` |
| RAG retrieval | `lightrag-hku` (also `lightrag-hku[api]` for server mode) |
| Structured LLM | `instructor` |
| Mindmap (JS) | `markmap-lib` (npm) + `markmap-cli` |
| Quiz UI (JS) | `react-quiz-component` (npm, needs React 19) |
| Video editing | `moviepy` (v2) |
| Vector DB | `chromadb` |

## File conventions

- All API routes in `app/routers/`, one file per feature domain.
- All business logic in `app/services/`, no direct DB access from routers.
- Pydantic schemas in `app/models/schemas.py` — request/response models only.
- Configuration via `app/config.py` using `pydantic-settings` with `.env` file.
- Static frontend assets in `static/`, served by FastAPI's `StaticFiles` mount.
- No implicit relative imports; always use `from app.X import Y`.

## Quy tắc Điều phối Tự động (Subagent Handoff Rules)

1. Khi Architect Agent (hoặc bất kỳ Primary Agent nào) hoàn thành phân tích và xác định xong bước tiếp theo:
   - **KHÔNG ĐƯỢC** dừng lại để hỏi câu hỏi dạng "Bạn có muốn tôi chuyển giao không?".
   - **PHẢI TỰ ĐỘNG** gọi (invoke) Subagent tương ứng (ví dụ: `backend-ai-agent`) bằng công cụ/Subagent Tool có sẵn để thực thi công việc ngay lập tức.
2. Trả về kết quả cho người dùng CHỈ KHI toàn bộ chuỗi công việc của bước đó đã được Subagent hoàn thành hoặc gặp lỗi nghiêm trọng không thể tự gỡ.