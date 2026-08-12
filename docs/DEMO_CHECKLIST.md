# PenG Demo Checklist

Use this checklist for the final presentation and for a clean Colab rehearsal.

## Before the demo

- Use a fresh Google Colab T4 runtime.
- Run `notebooks/peng_colab.ipynb` from the first cell.
- Set the ngrok token through Colab Secrets or an environment variable.
- Confirm `/api/health` returns HTTP 200 and `db: ok`.
- Upload one small PDF with native text and wait for `completed`.
- Keep a second small image available to demonstrate OCR fallback.
- Confirm the Qwen2.5-1.5B model has already been downloaded or allow a few minutes.
- Open the public URL in an incognito window and verify the frontend loads.

## Presentation flow

1. Upload the PDF and show checksum-backed document/job creation.
2. Show the queued → processing → completed job lifecycle.
3. Ask one question whose answer is directly present in the document.
4. Generate a four-option quiz and submit a mix of correct and incorrect answers.
5. Generate a mindmap, zoom it, and download Markdown/SVG.
6. Open History and show the recorded activities and score.
7. Briefly explain extraction → embedding → LightRAG → Qwen → structured output.

## Fallback plan

- If answer quality is insufficient, switch to `Qwen/Qwen2.5-3B-Instruct`.
- If the model is still warming up, demonstrate upload, job polling, and OCR first.
- If ngrok fails, use `http://localhost:8000` inside the notebook runtime.
- Keep a screenshot or short screen recording of a successful full run.

## Evidence to prepare

- Public GitHub repository URL.
- GitHub release URL and version tag.
- README installation section.
- Test output showing unit tests passed.
- One architecture diagram and one AI pipeline diagram.
- Third-party license/notice document.
