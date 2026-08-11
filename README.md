# PenG — AI Học Tập Thông Minh

Ứng dụng học tập đa năng: upload tài liệu (audio, ảnh, PDF, video), tự động trích xuất nội dung, tạo mindmap và câu hỏi ôn tập bằng AI.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-48%20passed-brightgreen.svg)](tests/)

PenG là phần mềm nguồn mở. License của PenG chỉ áp dụng cho mã nguồn của dự án;
model weights, OCR engine, FFmpeg, PyMuPDF và các dependency bên thứ ba có điều
khoản riêng. Xem [Third-party notices](docs/THIRD_PARTY_NOTICES.md).

## Kiến trúc

```
┌──────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│  Upload  │────▶│  Extract (STT/OCR/Video) │────▶│  Index (RAG)     │
│  (API)   │     │  - faster-whisper        │     │  - LightRAG      │
│          │     │  - Tesseract / Surya     │     │  - NanoVectorDB  │
│          │     │  - scenedetect+MoviePy   │     │                  │
└──────────┘     └─────────────────────────┘     └──────┬───────────┘
                                                        │
                    ┌───────────────────────────────────┘
                    ▼
┌──────────┐  ┌─────────────┐  ┌──────────────────────┐
│  Query   │─▶│   LLM       │─▶│  Structured Output   │
│  (API)   │  │ Llama/Qwen  │  │  - Pydantic + retry   │
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
| OCR | pytesseract (mặc định) / EasyOCR / Surya (Python <=3.11) + PyMuPDF + Pillow | Surya yêu cầu Pillow<11; không cài trong requirements.txt local |
| Video | scenedetect + MoviePy | Keyframe extraction + OCR |
| RAG | LightRAG (`lightrag-hku`) | Naive mode (vector-only), không cần graph |
| Vector DB | NanoVectorDB (file-based) | Mặc định trong LightRAG 1.5.5 |
| LLM | Qwen2.5-3B-Instruct (mặc định) / Llama-3.2-3B | 4-bit quantize trên Colab T4 |
| Structured Output | JSON + Pydantic + bounded retry | Instructor chỉ là adapter tùy chọn |
| Mindmap | Markmap (`markmap-lib`) | Render markdown → mindmap |
| Quiz UI | Vanilla JavaScript | Không cần React build |
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

Các lệnh trên phải được chạy từ thư mục repository. Ứng dụng cũng hỗ trợ chạy từ
thư mục khác sau khi cài package, vì các path mặc định được resolve theo project
root; biến môi trường trong `.env` có thể dùng path tuyệt đối để tách dữ liệu runtime.

Model Qwen và embedding sẽ được tải ở lần chạy đầu tiên. Unit test không tải model;
hãy chạy integration test riêng khi runtime đã có GPU, FFmpeg và OCR system packages.

## Dependencies hệ thống

Các gói Python sau **không** được cài bằng `pip` và cần có sẵn trên máy:

| Công cụ | Mục đích | Cài đặt gợi ý |
|---------|----------|---------------|
| ffmpeg | Giải mã audio/video cho STT, scenedetect, MoviePy | Ubuntu/Debian: `sudo apt-get install ffmpeg` |
| Tesseract OCR | OCR mặc định cho ảnh và PDF | Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng` |
| Tesseract language packs | Tiếng Việt + tiếng Anh | `tesseract-ocr-vie` và `tesseract-ocr-eng` |

Trên **Windows**, tải [Tesseract installer](https://github.com/UB-Mannheim/tesseract/wiki) và thêm vào `PATH`. Trên **Google Colab**, các gói này thường đã có sẵn; nếu thiếu chạy `!apt-get update && apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng`.

## API Endpoints

| Method | Route | Mô tả |
|--------|-------|-------|
| GET | `/api/health` | Kiểm tra server và SQLite |
| POST | `/api/upload` | Upload file (audio/image/pdf/video) |
| GET | `/api/jobs/{job_id}` | Trạng thái xử lý tài liệu |
| GET | `/api/query?q=...` | Truy vấn tài liệu đã index |
| POST | `/api/quiz/generate` | Tạo câu hỏi ôn tập |
| GET | `/api/quiz/{quiz_id}` | Lấy bộ quiz đã lưu |
| POST | `/api/quiz/{quiz_id}/submit` | Nộp đáp án và chấm điểm |
| GET | `/api/mindmap/{doc_id}` | Lấy mindmap (markdown) |
| GET | `/api/history` | Lịch sử học tập |
| POST | `/api/history` | Ghi log hoạt động |

## Chạy trên Google Colab

1. Clone repo:
```python
!git clone https://github.com/canhcutlo/PenG.git
%cd PenG
```

2. Cài đặt (Colab dùng `requirements-colab.txt` đã bao gồm pyngrok và pin Pillow cho Surya):
```python
!pip install -r requirements-colab.txt
```

3. Thiết lập ngrok (token qua biến môi trường/Secret, không ghi trực tiếp vào notebook):
```python
from pyngrok import ngrok
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
├── README.md              # Bạn đang ở đây
├── LICENSE               # MIT License
├── CHANGELOG.md          # Lịch sử thay đổi
├── CONTRIBUTING.md       # Hướng dẫn đóng góp
├── SECURITY.md           # Báo cáo lỗ hổng
├── docs/                 # Kiến trúc, AI pipeline, third-party notices
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
│   │   ├── quiz_gen.py    #   Quiz generation
│   │   └── mindmap_gen.py #   Mindmap generation
│   ├── db/                # Database layer
│   │   └── sqlite_store.py
│   ├── models/
│   │   └── schemas.py     # Pydantic models
│   └── utils/
│       └── file_utils.py
├── static/                # Frontend HTML/JS
├── tests/
│   └── test_*.py          # API, config, extraction, RAG, structured tests
└── notebooks/
    └── peng_colab.ipynb   # Google Colab notebook
```

## Lưu ý quan trọng

- **Python >=3.10** bắt buộc (LightRAG requirement).
- `scenedetect` KHÔNG phải `pyscenedetect` — pip install đúng tên.
- OCR mặc định là **pytesseract**; Surya chỉ dùng được trên Python <=3.11 (yêu cầu Pillow<11) và phải cài riêng.
- "Unlimited-OCR" không tồn tại — dùng Surya OCR, pytesseract hoặc EasyOCR.
- GPU Colab T4 (≈15GB): luôn dùng 4-bit quantization cho LLM.
- MoviePy v2 có API khác v1 — code trong project này dùng v2.
- Unit test: `pytest tests/ -v -m "not integration"`; integration test mới tải model AI.
- Runtime paths trong `.env` có thể để tương đối (sẽ resolve từ project root) hoặc tuyệt đối.

## Tài liệu dự án

- [AI pipeline](docs/AI_PIPELINE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Third-party notices](docs/THIRD_PARTY_NOTICES.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Demo checklist](docs/DEMO_CHECKLIST.md)
