---
description: Tạo virtual environment và cài đặt tất cả dependencies cho dự án PenG
agent: backend-ai-agent
---

Thực hiện các bước sau theo thứ tự:

1. Tạo virtual environment: `python -m venv .venv`
2. Activate: `.venv\Scripts\Activate.ps1` (Windows) hoặc `source .venv/bin/activate` (Linux/Mac)
3. Cài dependencies: `pip install -r requirements.txt`
4. Kiểm tra: `python -m compileall app`
5. Báo cáo kết quả: packages nào cài thành công, packages nào lỗi.

Lưu ý:
- Python phải >=3.10.
- Nếu gặp lỗi CUDA/cuDNN với faster-whisper, pin `ctranslate2==3.24.0`.
- Không tự ý thay đổi requirements.txt.
