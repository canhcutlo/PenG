# PenG — AI Học Tập Thông Minh

Ứng dụng học tập đa năng: upload tài liệu (audio, ảnh, PDF, video), tự động trích xuất nội dung, tạo mindmap và câu hỏi ôn tập bằng AI.

## Kiến trúc

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────┐
│  Upload  │────▶│  Extract (STT/OCR/Video) │────▶│  Index (RAG) │
│  (API)   │     │  - faster-whisper        │     │  - LightRAG   │
│          │     │  - Surya OCR             │     │  - ChromaDB   │
│          │     │  - scenedetect+MoviePy   │     │               │
└──────────┘     └─────────────────────────┘     └──────┬───────┘
                                                        │
                    ┌───────────────────────────────────┘
                    ▼
┌──────────┐  ┌─────────────┐  ┌──────────────────────┐
│  Query   │─▶│   LLM       │─▶│  Structured Output   │
│  (API)   │  │ Llama/Qwen  │  │  - Instructor        │
└──────────┘  └─────────────┘  └──────┬───────────────┘
                                       │
                          ┌────────────┼────────────┐
                          ▼            ▼            ▼
                    ┌──────────┐ ┌──────────┐ ┌──────────┐
                    │ Mindmap  │ │  Quiz    │ │ History  │
                    │ (Markmap)│ │(react QC)│ │ (SQLite) │
                    └──────────┘ └──────────┘ └──────────┘
```

## Tech Stack

| Lớp | Công nghệ | Ghi chú |
|------|-----------|---------|
| Backend | FastAPI + Uvicorn | Python >=3.10 |
| STT | faster-whisper | Model `base`, dùng CUDA nếu có |
| OCR | Surya (Colab/Python 3.11) / pytesseract / EasyOCR + PyMuPDF + Pillow | Surya không hỗ trợ Python 3.14 |
| Video | scenedetect + MoviePy | Keyframe extraction + OCR |
| RAG | LightRAG (`lightrag-hku`) | Naive mode (vector-only), không cần graph |
| Vector DB | NanoVectorDB (file-based) | Mặc định trong LightRAG 1.5.5 |
| LLM | Qwen2.5-3B-Instruct (mặc định) / Llama-3.2-3B | 4-bit quantize trên Colab T4 |
| Structured Output | Instructor | Sinh quiz, summary |
| Mindmap | Markmap (`markmap-lib`) | Render markdown → mindmap |
| Quiz UI | react-quiz-component | React 19 component |
| History | SQLite | Lịch sử học tập |
| Colab | ngrok (`pyngrok`) | Public endpoint cho FastAPI |

## Cài đặt

```powershell
# Tạo venv
python -m venv .venv
.venv\Scripts\Activate.ps1

# Cài dependencies
pip install -r requirements.txt

# Chạy server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test (unit — không tải model)
pytest tests/ -v -m "not integration"

# Test tất cả (tải model AI)
pytest tests/ -v
```

## API Endpoints

| Method | Route | Mô tả |
|--------|-------|-------|
| POST | `/api/upload` | Upload file (audio/image/pdf/video) |
| GET | `/api/query?q=...` | Truy vấn tài liệu đã index |
| POST | `/api/quiz/generate` | Tạo câu hỏi ôn tập |
| GET | `/api/quiz/attempt?quiz_id=...` | Lấy bộ quiz |
| POST | `/api/quiz/submit` | Nộp đáp án |
| GET | `/api/mindmap/{doc_id}` | Lấy mindmap (markdown) |
| GET | `/api/mindmap/{doc_id}/html` | Mindmap dạng HTML |
| GET | `/api/history` | Lịch sử học tập |
| POST | `/api/history` | Ghi log hoạt động |

## Chạy trên Google Colab

1. Clone repo:
```python
!git clone https://github.com/canhcutlo/PenG.git
%cd PenG
```

2. Cài đặt:
```python
!pip install -r requirements.txt
!pip install pyngrok
```

3. Thiết lập ngrok:
```python
from pyngrok import ngrok
ngrok.set_auth_token("YOUR_NGROK_TOKEN")
public_url = ngrok.connect(8000)
print(public_url)
```

4. Chạy server:
```python
import uvicorn
uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
```

## Cấu trúc thư mục

```
PenG/
├── AGENTS.md              # Hướng dẫn cho AI assistant
├── README.md              # Bạn đang ở đây
├── requirements.txt       # Python dependencies
├── .gitignore
├── app/
│   ├── main.py            # FastAPI entrypoint
│   ├── config.py          # Configuration (pydantic-settings)
│   ├── routers/           # API routes
│   │   ├── upload.py      #   File upload
│   │   ├── query.py       #   RAG query
│   │   ├── quiz.py        #   Quiz endpoints
│   │   ├── mindmap.py     #   Mindmap endpoints
│   │   └── history.py     #   Learning history
│   ├── services/          # Business logic
│   │   ├── extractor.py   #   Extraction orchestrator
│   │   ├── stt.py         #   Speech-to-text
│   │   ├── ocr.py         #   Image/PDF OCR
│   │   ├── video.py       #   Video analysis
│   │   ├── rag.py         #   LightRAG integration
│   │   ├── llm.py         #   LLM + embeddings
│   │   ├── quiz_gen.py    #   Quiz generation (Instructor)
│   │   └── mindmap_gen.py #   Mindmap generation
│   ├── db/                # Database layer
│   │   ├── sqlite_store.py
│   │   └── chroma_store.py
│   ├── models/
│   │   └── schemas.py     # Pydantic models
│   └── utils/
│       └── file_utils.py
├── static/                # Frontend HTML/JS
├── tests/
│   └── test_api.py
└── notebooks/
    └── peng_colab.ipynb   # Google Colab notebook
```

## Lưu ý quan trọng

- **Python >=3.10** bắt buộc (LightRAG requirement).
- `scenedetect` KHÔNG phải `pyscenedetect` — pip install đúng tên.
- "Unlimited-OCR" không tồn tại — dùng Surya OCR (Python <=3.11), pytesseract/EasyOCR (Python 3.14+).
- GPU Colab T4 (≈15GB): luôn dùng 4-bit quantization cho LLM.
- MoviePy v2 có API khác v1 — code trong project này dùng v2.
- Unit test: `pytest tests/ -v -m "not integration"`; integration test mới tải model AI.
