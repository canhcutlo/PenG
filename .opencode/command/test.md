---
description: Chạy compile check và unit test (không tải model lớn)
agent: backend-ai-agent
---

Chạy theo thứ tự:

1. `python -m compileall app` — kiểm tra syntax toàn bộ app
2. `pytest tests/ -v -m "not integration"` — chạy unit test, bỏ qua test cần model

Nếu thất bại:
- Báo lỗi cụ thể (file, dòng, traceback).
- Không tự sửa nếu chưa hiểu nguyên nhân.
- Cập nhật `Plan.md` nhật ký với kết quả PASS/FAIL.

Sau khi pass: cập nhật `Plan.md` nhật ký.
