# PenG — AI Học Tập Thông Minh

Ứng dụng học tập đa năng: upload tài liệu (audio, ảnh, PDF, video), tự động trích xuất nội dung, tạo mindmap và câu hỏi ôn tập bằng AI.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-140%20passed-brightgreen.svg)](tests/)
[![Issues](https://img.shields.io/github/issues/canhcutlo/PenG)](https://github.com/canhcutlo/PenG/issues)
[![Release](https://img.shields.io/github/v/release/canhcutlo/PenG)](https://github.com/canhcutlo/PenG/releases)

## Giấy phép mở & Mục đích cấp phép (OSI-Approved License)

PenG là phần mềm nguồn mở được cấp phép hoàn toàn theo **[MIT License](LICENSE)** — một giấy phép tự do nguồn mở được tổ chức **OSI (Open Source Initiative)** công nhận và phê chuẩn.

- **Mục đích cấp phép:** Trao toàn quyền tự do cho người dùng, học sinh, sinh viên, giảng viên và các nhà nghiên cứu được tự do sử dụng, nghiên cứu mã nguồn, chỉnh sửa, tích hợp và tái phân phối phần mềm cho mọi mục đích học tập và phát triển phi thương mại hoặc thương mại mà không có bất kỳ rào cản độc quyền nào.
- **Chuẩn SPDX:** 100% các tệp mã nguồn Python (`.py`) và tệp giao diện tĩnh (`static/index.html`) trong dự án đều được gắn định danh bản quyền chuẩn SPDX (`SPDX-License-Identifier: MIT`) ở đầu tệp.
- **Giải trình tính tương thích giấy phép & Tính Module hóa:**
  - PenG tuân thủ nguyên tắc kiến trúc module hóa phân tách độc lập (*loose coupling* / *modular separation*).
  - Đối với thư viện `PyMuPDF` (sử dụng giấy phép kép GNU AGPL-3.0 hoặc giấy phép thương mại Artifex): PenG sử dụng PyMuPDF độc lập như một công cụ trích xuất văn bản (*isolated extraction utility*), không can thiệp, không sửa đổi, không liên kết tĩnh (*static link*) và không kế thừa mã nguồn của PyMuPDF. Tầng trích xuất tài liệu được thiết kế dạng plugin/adapter linh hoạt, cho phép người dùng thay thế hoàn toàn bằng Tesseract OCR, EasyOCR hoặc các thư viện trích xuất thuần Python khác khi cần mà không ảnh hưởng tới lõi hệ thống.
  - Mã nguồn cốt lõi của PenG hoàn toàn giữ trọn giấy phép MIT License mở và tương thích tuyệt đối. Chi tiết kiểm toán giấy phép bên thứ ba xem tại [Third-party notices](docs/THIRD_PARTY_NOTICES.md).

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
| LLM | Qwen2.5-1.5B-Instruct (mặc định) / Qwen2.5-3B-Instruct | 4-bit quantize trên Colab T4 |
| LLM (optional CPU) | GGUF via `llama-cpp-python` | `experiment/gguf-llama-cpp`; xem `docs/CPU_GGUF.md` |
| Structured Output | JSON + Pydantic + bounded retry | Instructor chỉ là adapter tùy chọn |
| Mindmap | Markmap (`markmap-lib`) | Render markdown → mindmap |
| Quiz UI | Vanilla JavaScript | Không cần React build |
| History | SQLite | Lịch sử học tập |
| Colab | ngrok (`pyngrok`) | Public endpoint cho FastAPI |

## Cài đặt và dịch từ mã nguồn (Building & Installing from Source)

Dự án PenG tuân thủ chuẩn đóng gói hiện đại của Python theo **PEP 517 / PEP 621** (sử dụng `setuptools` build backend). Bạn có thể cài đặt, biên dịch gói phân phối mở hoặc khởi chạy ứng dụng theo các hướng dẫn dưới đây:

### 1. Cài đặt trực tiếp từ mã nguồn
```bash
# Tạo và kích hoạt môi trường ảo (khuyến nghị)
python -m venv .venv
# Trên Windows:
.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
# source .venv/bin/activate

# Cài đặt trực tiếp package cùng dependencies từ source:
pip install .

# Hoặc cài đặt ở chế độ Editable (dành cho nhà phát triển/đóng góp code):
pip install -e .
```

### 2. Biên dịch gói phân phối mở (sdist & wheel)
Để đóng gói bản phân phối chuẩn mở theo chuẩn PEP 517 (tạo file source distribution `.tar.gz` và binary wheel `.whl` trong thư mục `dist/`):
```bash
# Cài đặt công cụ build chuẩn PEP 517
python -m pip install build

# Biên dịch gói mã nguồn mở và wheel
python -m build
```
Ngoài ra, bạn có thể tạo gói mã nguồn mở độc lập (open format `.tar.gz`) phục vụ lưu trữ hoặc nộp bài thi thẩm định:
```bash
python scripts/package_release.py
```
Gói nén sẽ được tạo tự động tại `dist/PenG-1.1.0.tar.gz` (loại bỏ an toàn `.git`, cache, môi trường ảo và model weights lớn).

### 3. Khởi chạy từ bất kỳ thư mục nào bằng lệnh CLI
Sau khi cài đặt package, PenG cung cấp lệnh CLI `peng-server` (entrypoint được khai báo trong `pyproject.toml`) cho phép khởi chạy Uvicorn server từ bất kỳ đâu trên hệ thống:
```bash
# Khởi chạy server mặc định (127.0.0.1:8000)
peng-server

# Hoặc tùy biến host, port và bật chế độ reload:
peng-server --host 0.0.0.0 --port 8000 --reload
```

### 4. Chạy kiểm thử (Testing)
```bash
# Chạy toàn bộ unit tests và functional tests (không tải model AI nặng)
pytest tests/ -v -m "not integration"

# Chạy kiểm thử tích hợp (yêu cầu GPU, FFmpeg, Tesseract)
pytest tests/ -v
```

Các lệnh trên phải được chạy từ thư mục repository. Ứng dụng cũng hỗ trợ chạy từ
thư mục khác sau khi cài package, vì các path mặc định được resolve theo project
root; biến môi trường trong `.env` có thể dùng path tuyệt đối để tách dữ liệu runtime.

Model Qwen và embedding sẽ được tải ở lần chạy đầu tiên. Unit test không tải model;
hãy chạy integration test riêng khi runtime đã có GPU, FFmpeg và OCR system packages.

### Optional CPU/GGUF runtime

Thương nhánh `experiment/gguf-llama-cpp` hỗ trợ chạy LLM bằng file GGUF cục bộ
qua `llama-cpp-python`, phù hợp máy không có GPU. Xem hướng dẫn chi tiết trong
[`docs/CPU_GGUF.md`](docs/CPU_GGUF.md). Runtime này là tùy chọn; mặc định vẫn
là Transformers/BitsAndBytes cho CUDA.

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

## Chia sẻ máy chủ qua Cloudflare Tunnel

Repo có kèm sẵn `cloudflared.exe` (bản Windows) để mở public endpoint tạm thời mà không cần mở cổng router hay cấu hình DNS:

```powershell
# Cửa sổ 1 — chạy server PenG
peng-server --host 0.0.0.0 --port 8000

# Cửa sổ 2 — mở quick tunnel trỏ về server đang chạy
.\cloudflared.exe tunnel --url http://localhost:8000
```

`cloudflared` sẽ in ra một URL dạng `https://<tên-ngẫu-nhiên>.trycloudflare.com`. Mở URL đó để truy cập PenG từ máy khác hoặc chia sẻ cho người khác dùng thử.

Khi truy cập qua HTTPS, bật cookie bảo mật trong `.env`:

```env
AUTH_COOKIE_SECURE=true
```

Lưu ý:

- Quick tunnel không cần tài khoản Cloudflare, nhưng URL đổi sau mỗi lần chạy — chỉ phù hợp cho demo/thử nghiệm, không dùng cho production.
- Trên Linux/macOS, tải nhị phân `cloudflared` của hệ điều hành tương ứng thay vì dùng file `.exe`.
- Nếu server chạy trong Docker/Colab, thay `http://localhost:8000` bằng địa chỉ thực tế của server.

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

## Quản lý lỗi & Đóng góp (Bug Tracker & Community)

PenG khuyến khích sự tham gia đóng góp, phản hồi và hoàn thiện từ cộng đồng nguồn mở:

- **Hệ thống theo dõi lỗi & Tính năng (Bug Tracker):** Nếu gặp lỗi trong quá trình sử dụng, triển khai hoặc muốn đề xuất tính năng mới, vui lòng mở issue trực tiếp tại [GitHub Issues](https://github.com/canhcutlo/PenG/issues).
- **Mẫu báo cáo chuẩn (Issue Templates):** Dự án cung cấp sẵn các biểu mẫu chuẩn tại [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/) gồm biểu mẫu báo cáo lỗi chi tiết (`bug_report.md`) và biểu mẫu đề xuất tính năng mới (`feature_request.md`).
- **Quy trình đóng góp (Contributing Guidelines):** Vui lòng đọc kỹ hướng dẫn đóng góp mã nguồn, chuẩn phong cách code và quy trình kiểm thử trong [CONTRIBUTING.md](CONTRIBUTING.md) trước khi tạo Pull Request.
- **Chính sách báo cáo bảo mật:** Để báo cáo an toàn các lỗ hổng bảo mật tiềm ẩn, vui lòng tham khảo [SECURITY.md](SECURITY.md).

## Tài liệu dự án

- [AI pipeline](docs/AI_PIPELINE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Third-party notices](docs/THIRD_PARTY_NOTICES.md)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Demo checklist](docs/DEMO_CHECKLIST.md)

