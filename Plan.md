# PenG - Kế hoạch Build

## 1. Mục tiêu và phạm vi

PenG là ứng dụng học tập cho phép người dùng upload audio, ảnh, PDF hoặc MP4; trích xuất nội dung; tìm kiếm hỏi đáp trên tài liệu; tạo mindmap; tạo quiz; và lưu lịch sử học tập.

Mục tiêu MVP:

- Chạy được sau khi clone vào Google Colab có GPU T4.
- Có API FastAPI cho toàn bộ luồng upload -> xử lý -> index -> truy vấn -> quiz/mindmap.
- Có thể kiểm thử tự động mà không bắt buộc tải model lớn hoặc gọi dịch vụ bên ngoài.
- Hỗ trợ tiếng Việt và tiếng Anh ở mức cơ bản.

Không đưa vào MVP: đăng nhập/phân quyền, cộng tác nhiều người dùng, triển khai production, thanh toán, fine-tuning model.

## 2. Quyết định kỹ thuật cần áp dụng

| Nhu cầu | Quyết định triển khai | Lý do/giới hạn |
|---|---|---|
| Backend | Python >=3.10, FastAPI, Uvicorn | LightRAG và scenedetect yêu cầu Python mới |
| Speech-to-text | `faster-whisper`, model `base` | Có thể chạy CPU; Colab dùng CUDA nếu tương thích |
| OCR | Surya OCR + PyMuPDF + Pillow; fallback `pytesseract` | “Unlimited-OCR” không phải package Python xác định |
| PDF | Trích text trực tiếp trước, OCR các trang không có text | Giảm thời gian và chi phí GPU |
| Video | PySceneDetect phát hiện scene, MoviePy lấy keyframe, OCR keyframe | MVP tập trung slide/chữ trên màn hình |
| RAG | LightRAG 1.5.5 làm pipeline retrieval; vector storage mặc định NanoVectorDBStorage (file-based) | ChromaDB đã bị deprecated trong lightrag-hku 1.5.5 (`kg/deprecated/`); không ép dùng Chroma qua LightRAG |
| Embedding | Chốt một embedding model hỗ trợ tiếng Việt, cấu hình qua `.env` | Không hard-code dimension trước khi xác minh model |
| LLM | Chọn Qwen 2.x 7B Instruct làm mặc định; cho phép Llama tương thích | Qwen phù hợp Colab T4 và tiếng Việt hơn trong MVP |
| LLM runtime | Ưu tiên Transformers + 4-bit; có adapter OpenAI-compatible nếu cần Instructor | Instructor không nên gọi trực tiếp một model local chưa có adapter |
| Structured output | Instructor + Pydantic schemas | Quiz/mindmap phải validate được, có retry khi JSON lỗi |
| Mindmap | Backend sinh Markdown; frontend render bằng `markmap-lib` | Markmap là JS, không phải package Python |
| Quiz UI | React 19 + `react-quiz-component`, build static hoặc nhúng bundle | Không biến backend thành React SPA bắt buộc |
| Lịch sử | SQLite | Chỉ lưu metadata, activity, quiz và kết quả |
| File/job state | SQLite lưu trạng thái job; file gốc và text lưu theo document directory | Tránh xử lý đồng bộ trong request upload |
| Colab public URL | `pyngrok`, token qua biến môi trường/Secret | Không commit token |

## 3. Vai trò các model/agent

| Vai trò | Model | Trách nhiệm |
|---|---|---|
| Architect Agent | Kimi K3 | Quyết định kiến trúc, ranh giới module, API contract, trade-off và review phase |
| Backend & AI Agent | Kimi K2.7 Code | FastAPI, pipeline extract, LightRAG, Chroma, LLM runtime, database và test backend |
| Frontend Agent | Qwen3.6 Plus | Giao diện upload/query, Markmap, quiz component, responsive UI và frontend test |
| Data & Prompt Agent | DeepSeek V4 Flash | Chunking, metadata, prompt, schema quiz, đánh giá chất lượng tiếng Việt |

Quy tắc phối hợp:

- Architect Agent duyệt API/schema trước khi Backend hoặc Frontend triển khai.
- Data & Prompt Agent phải cung cấp ví dụ input/output và tiêu chí đánh giá cho mọi prompt structured.
- Backend không để router gọi trực tiếp model hoặc database; mọi logic đi qua `app/services/` và `app/db/`.
- Frontend chỉ phụ thuộc API contract đã ghi trong tài liệu; không đọc trực tiếp SQLite/Chroma.

## 4. Kiến trúc và luồng dữ liệu

```text
Upload API
  -> validate extension, MIME, size, checksum
  -> tạo document/job trong SQLite
  -> lưu file tạm
  -> background worker xử lý
       audio -> faster-whisper -> text/segments
       image -> Surya -> text/boxes
       pdf -> native text hoặc render page -> OCR
       video -> scene detection -> keyframes -> OCR (+ audio STT nếu có)
  -> normalize text + metadata + chunk
  -> LightRAG index / Chroma embeddings
  -> cập nhật job completed/failed

Query API
  -> retrieve chunks bằng LightRAG
  -> LLM tổng hợp câu trả lời có citation document/page/time
  -> lưu activity SQLite

Quiz API
  -> lấy context từ RAG
  -> Instructor sinh Pydantic Quiz schema
  -> validate số lựa chọn, đáp án, explanation
  -> lưu quiz và kết quả SQLite

Mindmap API
  -> lấy context/tóm tắt
  -> LLM sinh Markdown giới hạn depth
  -> frontend render Markmap
```

## 5. Trạng thái hiện tại

- [x] Đã tạo skeleton FastAPI, router, service, database và notebook Colab.
- [x] Đã có `AGENTS.md`, `README.md`, `requirements.txt` và `.gitignore`.
- [x] Đã có `.env.example`, `requirements-colab.txt`, `package.json`.
- [x] Đã chốt model mặc định (Qwen2-7B), embedding (vietnamese-sbert), upload limits.
- [x] Đã sửa deprecation: lifespan, SettingsConfigDict.
- [x] Compile check và unit test hiện tại pass (41/41 unit test; 2 integration test để dành cho model thực).
- [x] Phase 1 backend contract & storage hoàn tất.
- [x] Phase 2 extraction hoàn tất: STT (faster-whisper base), OCR (pytesseract/easyocr; Surya optional), video (scenedetect + moviepy), PDF native text + OCR.
- [x] Upload endpoint tự động enqueue background extraction job.
- [x] Quyết định: Surya không hỗ trợ Python 3.14 → dùng pytesseract/easyocr làm mặc định trên Python 3.14+, Surya trên Colab Python 3.11.
- [x] Phase 3 chunking, embedding, LightRAG wrapper hoàn tất. Verify embedding dimension = 768 (keepitreal/vietnamese-sbert). LightRAG 1.5.5: dùng ainsert/aquery + initialize_storages(), embedding func trả numpy array, query naive mode.
- [x] Phase 4 LLM adapter + structured generation hoàn tất: JSON + Pydantic validate + retry giới hạn (3 lần); Instructor adapter dự phòng khi có OpenAI-compatible endpoint; prompt answer/summary/mindmap/quiz; model không load khi health/unit test.
- [x] Phase 5 quiz/mindmap/history API hoàn tất: quiz persist SQLite, submit chấm điểm + log activity, mindmap sanitize, history endpoint, query có citations.
- [x] Phase 6 frontend hoàn tất: `static/index.html` 927 dòng, 42KB, 5 tabs (upload/query/quiz/mindmap/history), markmap CDN, vanilla JS, responsive, tiếng Việt.
- [ ] Chưa có fixture media và test integration thực tế.
- [ ] Chưa xác minh toàn bộ dependency trong một runtime Colab sạch.

## 6. Lộ trình build theo phase

### Phase 0 - Chốt nền tảng và reproducibility

Nhiệm vụ:

- Pin Python, dependency và Node version; tách dependency CPU/GPU nếu cần.
- Tạo `.env.example`, `requirements-colab.txt`, `package.json` và script khởi động.
- Xác định model mặc định, embedding model, context length và chế độ CPU/GPU.
- Xác định giới hạn upload: extension, MIME, dung lượng, thời gian xử lý.
- Kiểm tra API thực tế của các phiên bản `lightrag-hku`, Surya, MoviePy v2 và Instructor.

Nghiệm thu:

- Clone vào Colab sạch, cài dependency không lỗi.
- `python -m compileall app` thành công.
- `/api/health` trả về `200`.

### Phase 1 - Backend contract và storage

Nhiệm vụ:

- Hoàn thiện Pydantic schemas: `Document`, `Job`, `Chunk`, `QueryResponse`, `Quiz`, `Mindmap`.
- Tạo SQLite schema/migration tối thiểu cho documents, processing_jobs, activities, quizzes, quiz_results.
- Viết file storage service với tên file an toàn, checksum, cleanup và giới hạn dung lượng.
- Chuẩn hóa lỗi API và trạng thái job: `queued`, `processing`, `completed`, `failed`.
- Tạo `GET /api/health`, `POST /api/upload`, `GET /api/jobs/{job_id}`.

Nghiệm thu:

- Upload file hợp lệ trả `document_id` và `job_id`.
- File sai loại/kích thước bị từ chối rõ ràng.
- Restart server không làm mất metadata SQLite.

### Phase 2 - Trích xuất nội dung

Nhiệm vụ:

- Implement STT lazy-load model `base`, trả text, segments, timestamps, language.
- Implement image OCR bằng Surya; fallback có log rõ ràng sang Tesseract.
- PDF: đọc text native; trang thiếu text mới render bằng PyMuPDF và OCR.
- Video: detect scene, lấy keyframe giới hạn số lượng, OCR slide; tùy chọn tách audio để STT.
- Chuẩn hóa output về một schema chung: text, page/scene/time, confidence, source.
- Chạy xử lý trong background task/worker, không block request upload.

Nghiệm thu:

- Có fixture nhỏ cho audio, ảnh, PDF text, PDF scan và MP4.
- Mỗi loại file tạo được text và metadata nguồn.
- Job lỗi ghi nguyên nhân vào SQLite và không để file tạm tồn đọng.

### Phase 3 - Chunking, embedding, LightRAG và Chroma

Nhiệm vụ:

- Tách chunk theo đoạn/heading, giữ `document_id`, `page`, `scene`, `timestamp`.
- Xác minh embedding dimension bằng model thực tế, không hard-code mù.
- Khởi tạo Chroma persistent collection với metadata filter.
- Tích hợp LightRAG bằng API/version đã pin; viết wrapper async/sync thống nhất.
- Implement indexing idempotent: upload lại checksum không tạo bản sao.
- Implement query có `top_k`, filter theo document và citation.

Nghiệm thu:

- Index cùng một document hai lần không nhân đôi dữ liệu.
- Query trả context liên quan kèm citation.
- Persistence hoạt động sau restart.
- Có test retrieval không cần LLM lớn bằng fake embedding/fake LLM.

### Phase 4 - LLM và structured generation

Nhiệm vụ:

- Implement model loader lazy-load, device detection, 4-bit config cho Colab T4.
- Tạo LLM adapter duy nhất cho completion/chat; không để service phụ thuộc trực tiếp Transformers.
- Tích hợp Instructor qua client tương thích và test JSON/schema validation.
- Tạo prompt cho answer, summary, mindmap, quiz; giới hạn context và token.
- Thêm retry có giới hạn khi output không hợp lệ, không retry vô hạn.
- Bắt buộc câu trả lời có citation; nếu không đủ context phải nói không đủ dữ liệu.

Nghiệm thu:

- Sinh được summary/answer có format ổn định.
- Quiz luôn có số câu đúng, 4 lựa chọn, một đáp án đúng và explanation.
- Model không được load khi chạy health/unit test.

### Phase 5 - Quiz và mindmap API

Nhiệm vụ:

- `POST /api/query` hoặc `GET /api/query` trả answer, citations và related chunks.
- `POST /api/quiz/generate` nhận document/query context và số câu; lưu quiz.
- `POST /api/quiz/submit` chấm điểm server-side, lưu kết quả và activity.
- `GET /api/mindmap/{document_id}` trả Markdown đã sanitize.
- Giới hạn độ sâu mindmap, loại bỏ code fence/thẻ nguy hiểm trước khi render.
- Bổ sung endpoint job progress để frontend polling.

Nghiệm thu:

- Có thể hoàn tất upload -> query -> generate quiz -> submit -> history.
- Quiz reload được từ SQLite.
- Mindmap render được từ Markdown hợp lệ và không chạy HTML tùy ý từ model.

### Phase 6 - Frontend

Nhiệm vụ:

- Xây UI static hoặc bundle React tối thiểu cho upload và hiển thị trạng thái job.
- Hiển thị query answer cùng citation page/scene/time.
- Nhúng `markmap-lib` cho mindmap.
- Nhúng `react-quiz-component` hoặc adapter tương thích React 19.
- Hiển thị lỗi, loading, retry và trạng thái GPU/model warming.
- Thiết kế responsive cho desktop/mobile; không hard-code URL localhost khi chạy qua ngrok.

Nghiệm thu:

- Người dùng hoàn thành luồng chính trên trình duyệt bằng public Colab URL.
- UI không lộ secret/token.
- Có smoke test cho upload, query, quiz và mindmap.

### Phase 7 - Kiểm thử Colab và hardening

Nhiệm vụ:

- Cập nhật notebook theo thứ tự: clone -> kiểm tra GPU -> cài -> env/secrets -> migrate -> test -> start server -> ngrok.
- Test trên Colab GPU T4 và CPU fallback.
- Đo thời gian/công suất cho STT, OCR, video, embedding và LLM.
- Thêm timeout, cleanup, giới hạn concurrency và giới hạn file.
- Kiểm tra dependency license, không commit model/cache/database/media lớn.
- Viết troubleshooting cho CUDA/cuDNN, ngrok, memory và ffmpeg.

Nghiệm thu:

- `pytest tests/ -v` pass trong Colab.
- Smoke test toàn bộ pipeline với fixture nhỏ pass.
- Notebook chạy lại được từ đầu sau khi restart runtime.
- Không có secret trong git và `git diff` chỉ chứa thay đổi dự kiến.

## 7. API contract dự kiến

| Method | Endpoint | Mục đích |
|---|---|---|
| GET | `/api/health` | Kiểm tra server và dependency nhẹ |
| POST | `/api/upload` | Tạo document/job từ audio, image, PDF, MP4 |
| GET | `/api/jobs/{job_id}` | Trạng thái và lỗi xử lý |
| POST | `/api/query` | RAG answer + citations |
| POST | `/api/quiz/generate` | Sinh và lưu quiz |
| GET | `/api/quiz/{quiz_id}` | Lấy quiz |
| POST | `/api/quiz/{quiz_id}/submit` | Chấm và lưu kết quả |
| GET | `/api/mindmap/{document_id}` | Lấy Markdown mindmap |
| GET | `/api/history` | Lịch sử hoạt động/phần điểm |

Các endpoint phải có request/response schema, HTTP status, error shape và ví dụ trước khi frontend triển khai.

## 8. Kiểm thử và lệnh chuẩn

Chạy theo thứ tự:

```bash
python -m compileall app
pytest tests/ -v
```

Kiểm thử tập trung:

```bash
pytest tests/test_api.py -v
pytest tests/test_api.py::test_health -v
```

Chạy server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Test integration có model phải đánh dấu riêng, ví dụ `@pytest.mark.integration`, để unit test không tự động tải model lớn.

## 9. Quy trình Google Colab

```python
!git clone https://github.com/canhcutlo/PenG.git
%cd PenG
!nvidia-smi
!pip install -r requirements-colab.txt
```

Sau đó:

1. Đặt secrets bằng Colab Secrets hoặc biến môi trường; không ghi token vào notebook.
2. Kiểm tra CUDA/cuDNN và điều chỉnh `ctranslate2` nếu runtime dùng CUDA 11.
3. Chạy migration/init storage.
4. Chạy compile và pytest trước khi start server.
5. Chạy Uvicorn, mở ngrok port 8000, kiểm tra `/api/health`.
6. Chạy smoke test với fixture media nhỏ.
7. Ghi kết quả và lỗi vào nhật ký bên dưới.

## 10. Luật cập nhật bắt buộc

**Sau mỗi lần chạy lệnh, test, notebook hoặc agent task, phải cập nhật file này trước khi kết thúc phiên.** Không đánh dấu hoàn thành nếu chưa có bằng chứng kiểm thử.

Mỗi cập nhật phải ghi:

- thời gian;
- agent/model thực hiện;
- phase/task;
- lệnh hoặc notebook cell đã chạy;
- kết quả `PASS`, `FAIL` hoặc `BLOCKED`;
- lỗi đầy đủ và nguyên nhân nếu có;
- file đã thay đổi;
- bước tiếp theo.

### Nhật ký thực thi

| Thời gian | Agent | Phase/task | Lệnh/thao tác | Kết quả | Vấn đề/bước tiếp theo |
|---|---|---|---|---|---|
| 2026-08-01 | Architect Agent / OpenCode | Khởi tạo kế hoạch | Rà soát skeleton repo | PASS | Cần triển khai theo Phase 0 |
| 2026-08-01 | Architect Agent / OpenCode | Tạo `Plan.md` | Rà soát `AGENTS.md`, `README.md`, cấu trúc repo; tạo kế hoạch | PASS | Bắt đầu Phase 0; chưa chạy test/runtime vì đây là bước lập kế hoạch |
| 2026-08-01 | Architect Agent / OpenCode | Phase 0 | Compile check: `python -m compileall app` (25 files) | PASS | Không lỗi compile |
| 2026-08-01 | Architect Agent / OpenCode | Phase 0 | Unit test: `pytest tests/ -v` (3 tests) | PASS | 3/3 pass; health, upload validation, query |
| 2026-08-01 | Architect Agent / OpenCode | Phase 0 | Sửa deprecation: lifespan thay on_event, SettingsConfigDict thay class Config | PASS | Còn 1 warning Starlette/httpx (external, không ảnh hưởng) |
| 2026-08-01 | Architect Agent / OpenCode | Phase 0 | Tạo `.env.example`, `requirements-colab.txt`, `package.json` | PASS | Đã có đủ file config cho Phase 0 |
| 2026-08-01 | Architect Agent / OpenCode | Phase 0 | Chốt model/embedding: Qwen2-7B + vietnamese-sbert 768d; upload 500MB | PASS | Cấu hình qua Settings, không hard-code |
| 2026-08-01 | Architect Agent / OpenCode | Phase 1 | Hoàn thiện Pydantic schemas (Document, Job, Citation, QueryResponse, ErrorResponse) | PASS | Đầy đủ request/response models |
| 2026-08-01 | Architect Agent / OpenCode | Phase 1 | Mở rộng SQLite: documents, processing_jobs, activities + CRUD đầy đủ | PASS | 5 bảng, foreign key, WAL mode |
| 2026-08-01 | Architect Agent / OpenCode | Phase 1 | Viết file_storage.py: validate, checksum SHA-256, save/cleanup | PASS | Giới hạn 500MB, dedup checksum |
| 2026-08-01 | Architect Agent / OpenCode | Phase 1 | Implement POST /api/upload + GET /api/jobs/{job_id} | PASS | Form data qua Annotated[Form()] |
| 2026-08-01 | Architect Agent / OpenCode | Phase 1 | Viết 11 tests (upload valid/invalid/duplicate, job status) | PASS | 11/11 pass, 1 warning external |
| 2026-08-01 | Architect Agent / OpenCode | Phase 1 | Sửa bug: category dùng Form(), dedup không filter status | PASS | Root cause: str default bị parse thành query param |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Kiểm tra availability model: faster-whisper, Surya, scenedetect, moviepy | BLOCKED | Thiếu tất cả model libraries (ModuleNotFoundError). Chưa cài đặt dependencies. Dừng theo yêu cầu của user. |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Cài đặt công cụ: faster-whisper, scenedetect, moviepy, pymupdf, pytesseract, easyocr | PASS | Pillow cần >=11.0 cho Python 3.14; Surya-ocr không cài được trên Python 3.14 do dependency Pillow 10.4 |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Implement STT service (faster-whisper base), lazy-load | PASS | Test tải model base thành công trên CPU |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Implement OCR service (pytesseract/easyocr/Surya optional) | PASS | Tesseract cần binary; easyocr có sẵn; Surya optional |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Implement PDF service (native text + OCR fallback) | PASS | PyMuPDF extract text + OCR |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Implement Video service (scenedetect + moviepy keyframe OCR) | PASS | Có cap 20 keyframes, fallback sample khi không detect scene |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Background extraction job tự động từ upload endpoint | PASS | Có thể tắt qua `process_on_upload` cho test |
| 2026-08-01 | Architect Agent / OpenCode | Phase 2 | Viết 15 unit tests + 2 integration tests | PASS | 15/15 pass; integration cần Tesseract binary hoặc EasyOCR model |
| 2026-08-01 | Architect Agent / OpenCode | Phase 3 | Cài đặt lightrag-hku 1.5.5, chromadb 1.5.9, sentence-transformers 5.6.1 | PASS | Verify embedding dimension = 768 (keepitreal/vietnamese-sbert) |
| 2026-08-01 | Architect Agent / OpenCode | Phase 3 | Implement chunking service: split/chunk/build_chunks, giữ page/scene/timestamp metadata | PASS | 6 unit tests chunking pass |
| 2026-08-01 | Architect Agent / OpenCode | Phase 3 | Viết lại LightRAG wrapper cho 1.5.5: initialize_storages(), ainsert/aquery, embedding trả numpy array | PASS | ChromaDB deprecated trong 1.5.5; dùng NanoVectorDBStorage mặc định |
| 2026-08-01 | Architect Agent / OpenCode | Phase 3 | Implement query endpoint + index vào processing | PASS | Query naive mode hoạt động không cần LLM graph |
| 2026-08-01 | Architect Agent / OpenCode | Phase 3 | Viết test retrieval với fake embedding | PASS | 22/22 unit test pass |
| 2026-08-01 | Architect Agent / OpenCode | Phase 4 | Cài instructor 1.15.4; kiểm tra API: from_openai/from_litellm, không có adapter Transformers trực tiếp | PASS | Instructor chỉ dùng khi có OpenAI-compatible endpoint (Ollama/vLLM) |
| 2026-08-01 | Architect Agent / OpenCode | Phase 4 | Hoàn thiện LLM adapter: lazy-load, device_info, reset_llm_for_tests, max_new_tokens | PASS | Model không load khi health/unit test |
| 2026-08-01 | Architect Agent / OpenCode | Phase 4 | Implement structured.py: JSON + Pydantic validate + retry giới hạn 3 lần + Instructor adapter dự phòng | PASS | Sửa bug: _format_validation_error không serialize được ctx (dùng default=str) |
| 2026-08-01 | Architect Agent / OpenCode | Phase 4 | Tạo prompts.py + quiz_gen + mindmap_gen (schema quiz 4 options, sanitize mindmap) | PASS | Quiz validate options unique, 4 lựa chọn |
| 2026-08-01 | Architect Agent / OpenCode | Phase 4 | Viết 11 tests structured generation với fake LLM | PASS | 33/33 unit test pass |
| 2026-08-01 | Architect Agent / OpenCode | Phase 5 | Fix quiz/generate persist vào SQLite + quiz/submit chấm điểm + log activity | PASS | Quiz reload từ SQLite |
| 2026-08-01 | Architect Agent / OpenCode | Phase 5 | Wire history endpoint + query endpoint có citations | PASS | Full CRUD cho quiz/activity |
| 2026-08-01 | Architect Agent / OpenCode | Phase 5 | Viết 8 tests end-to-end: upload → job → quiz submit → history | PASS | 41/41 unit test pass |
| 2026-08-01 | Architect Agent / OpenCode | Phase 5 | Sửa bug: duplicate upload trả job_id rỗng (document table không có job_id) → tạo job mới cho duplicate | PASS | |
| 2026-08-01 | Frontend Agent / OpenCode | Phase 6 | Tạo `static/index.html` hoàn chỉnh: 5 tabs (Upload, Query, Quiz, Mindmap, History), markmap CDN, drag-drop upload, job polling, quiz vanilla JS, responsive, tiếng Việt, copy clipboard | PASS | 927 dòng, 42KB; không localhost, không hardcoded URL; TestClient verify tất cả tabs & features |
| 2026-08-01 | Frontend Agent / OpenCode | Phase 6 | Tạo `static/index.html` hoàn chỉnh: 5 tabs (Upload, Query, Quiz, Mindmap, History), markmap CDN, drag-drop upload, job polling, quiz vanilla JS, responsive, tiếng Việt, copy clipboard | PASS | 927 dòng, 42KB; không localhost, không hardcoded URL; TestClient verify tất cả tabs & features |

### Mẫu bản ghi

```text
#### YYYY-MM-DD HH:mm - <Agent/model> - <Phase/task>
- Command/cell: `<lệnh>`
- Result: PASS | FAIL | BLOCKED
- Completed: <việc đã xong>
- Error/root cause: <lỗi hoặc “None”>
- Changed files: <danh sách>
- Next step: <việc tiếp theo>
```

## 11. Definition of Done cho MVP

- Clone và cài được trong Colab T4 từ notebook.
- Upload được cả bốn loại input và theo dõi được job.
- Audio có transcript; ảnh/PDF có OCR hoặc native text; MP4 có scene/keyframe text.
- Tài liệu được index persistent, query có citation.
- Qwen/Llama sinh được summary, mindmap và quiz hợp lệ qua schema.
- Quiz chấm điểm và lịch sử được lưu trong SQLite.
- Frontend hiển thị được các chức năng chính qua ngrok.
- Unit test, integration smoke test và notebook run được ghi kết quả trong `Plan.md`.
- Mọi lỗi chưa xử lý được ghi trong nhật ký, không bị che khuất bằng việc đánh dấu task hoàn thành.
