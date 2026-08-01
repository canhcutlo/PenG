---
description: Cài đặt và chạy PenG trên Google Colab với GPU T4
agent: backend-ai-agent
---

Thực hiện tuần tự:

1. Kiểm tra GPU: `!nvidia-smi`
2. Clone repo: `!git clone https://github.com/canhcutlo/PenG.git && %cd PenG`
3. Cài dependency: `!pip install -r requirements-colab.txt`
4. Kiểm tra CUDA version — nếu CUDA 11, pin: `!pip install ctranslate2==3.24.0`
5. Biên dịch: `!python -m compileall app`
6. Chạy unit test: `!pytest tests/ -v -m "not integration"`
7. Khởi động server: 

```python
import uvicorn
import nest_asyncio
nest_asyncio.apply()
uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
```

8. Mở ngrok (nếu có token):

```python
from pyngrok import ngrok
# ngrok.set_auth_token("YOUR_TOKEN")
public_url = ngrok.connect(8000)
print(f"Public URL: {public_url}")
```

9. Smoke test: gọi `/api/health` từ public URL.

Cập nhật `Plan.md` với kết quả PASS/FAIL và mọi lỗi phát sinh.
